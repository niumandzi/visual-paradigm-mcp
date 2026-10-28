package local.codex;

import com.vp.plugin.*;
import com.vp.plugin.diagram.*;
import com.vp.plugin.model.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.net.URLClassLoader;
import java.util.Properties;
import javax.swing.Timer;
import javax.swing.SwingUtilities;

/** Local file transport; all model access runs on Visual Paradigm's EDT. */
public final class Bridge implements VPPlugin {
    private Path root;
    private Path ipc;
    private Timer timer;

    public void loaded(VPPluginInfo info) {
        SwingUtilities.invokeLater(() -> {
            try {
                Properties config = new Properties();
                try (java.io.Reader reader = Files.newBufferedReader(info.getPluginDir().toPath().resolve("bridge.properties"), StandardCharsets.UTF_8)) { config.load(reader); }
                String location = System.getProperty("vp.mcp.root", config.getProperty("root"));
                if (location == null || location.isEmpty()) throw new IllegalStateException("Missing bridge root in bridge.properties");
                root = Paths.get(location).toRealPath();
                ipc = root.resolve("ipc");
                Files.createDirectories(ipc);
                write(ipc.resolve("ready.json"), "{\"status\":\"ready\",\"pid\":" + ProcessHandle.current().pid() + "}");
                timer = new Timer(300, event -> poll());
                timer.start();
            } catch (Exception e) { e.printStackTrace(); }
        });
    }

    public void unloaded() {
        if (timer != null) timer.stop();
        try { if (ipc != null) Files.deleteIfExists(ipc.resolve("ready.json")); } catch (Exception e) { e.printStackTrace(); }
    }

    private void poll() {
        Path request = ipc.resolve("request.properties");
        if (!Files.exists(request)) return;
        String id = "unknown";
        try {
            Properties p = new Properties();
            try (java.io.Reader reader = Files.newBufferedReader(request, StandardCharsets.UTF_8)) { p.load(reader); }
            id = p.getProperty("id", "unknown");
            Files.delete(request); // Consume once; failed commands must never replay.
            if (!id.matches("[a-zA-Z0-9-]{1,80}")) throw new IllegalArgumentException("Invalid request id");
            ApplicationManager app = ApplicationManager.instance();
            String result;
            switch (p.getProperty("op", "snapshot")) {
                case "snapshot": result = snapshot(app); break;
                case "run":
                    String name = p.getProperty("class");
                    if (!"Command".equals(name)) throw new IllegalArgumentException("Only the MCP Command dispatcher is supported");
                    try (URLClassLoader loader = new URLClassLoader(new java.net.URL[]{root.resolve("jobs").toUri().toURL()}, getClass().getClassLoader())) {
                        Object value = loader.loadClass("Command").getMethod("run", ApplicationManager.class).invoke(null, app);
                        result = q(String.valueOf(value));
                    }
                    break;
                default: throw new IllegalArgumentException("Unknown operation");
            }
            write(ipc.resolve(id + ".json"), "{\"ok\":true,\"result\":" + result + "}");
        } catch (Throwable e) {
            try {
                if (!id.matches("[a-zA-Z0-9-]{1,80}")) id = "unknown";
                write(ipc.resolve(id + ".json"), "{\"ok\":false,\"error\":" + q(e.toString()) + "}");
            } catch (Exception failure) { failure.printStackTrace(); }
            e.printStackTrace();
        }
    }

    static String snapshot(ApplicationManager app) {
        IProject project = app.getProjectManager().getProject();
        if (project == null) return "null";
        IDiagramUIModel active = app.getDiagramManager().getActiveDiagram();
        StringBuilder out = new StringBuilder("{\"project\":").append(q(project.getName()))
            .append(",\"file\":").append(q(String.valueOf(project.getProjectFile())))
            .append(",\"modified\":").append(project.isModified())
            .append(",\"activeDiagramId\":").append(active == null ? "null" : q(active.getId()))
            .append(",\"diagrams\":[");
        boolean firstDiagram = true;
        for (IDiagramUIModel diagram : project.toDiagramArray()) {
            if (!firstDiagram) out.append(','); firstDiagram = false;
            out.append("{\"id\":").append(q(diagram.getId())).append(",\"name\":").append(q(diagram.getName()))
                .append(",\"type\":").append(q(diagram.getType())).append(",\"elements\":[");
            boolean firstElement = true;
            for (IDiagramElement element : diagram.toDiagramElementArray()) {
                if (!firstElement) out.append(','); firstElement = false;
                IModelElement model = element.getModelElement();
                out.append("{\"id\":").append(q(element.getId())).append(",\"shape\":").append(q(element.getShapeType()))
                    .append(",\"modelId\":").append(model == null ? "null" : q(model.getId()))
                    .append(",\"modelType\":").append(model == null ? "null" : q(model.getModelType()))
                    .append(",\"name\":").append(model == null ? "null" : q(model.getName()))
                    .append(",\"bounds\":[").append(element.getX()).append(',').append(element.getY()).append(',')
                    .append(element.getWidth()).append(',').append(element.getHeight()).append(']');
                if (element instanceof IConnectorUIModel) {
                    IConnectorUIModel c = (IConnectorUIModel) element;
                    out.append(",\"from\":").append(c.getFromShape() == null ? "null" : q(c.getFromShape().getId()))
                        .append(",\"to\":").append(c.getToShape() == null ? "null" : q(c.getToShape().getId()));
                }
                out.append('}');
            }
            out.append("]}");
        }
        return out.append("]}").toString();
    }

    private static String q(String s) {
        if (s == null) return "null";
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 32) b.append(String.format("\\u%04x", (int)c));
            else b.append(c);
        }
        return b.append('"').toString();
    }

    private static void write(Path path, String text) throws java.io.IOException {
        Path tmp = path.resolveSibling(path.getFileName() + ".tmp");
        Files.writeString(tmp, text, StandardCharsets.UTF_8);
        Files.move(tmp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
}
