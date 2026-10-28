import com.vp.plugin.*;
import com.vp.plugin.diagram.*;
import com.vp.plugin.model.*;
import com.vp.plugin.model.factory.IModelElementFactory;
import java.awt.Point;
import java.lang.reflect.Method;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.Properties;

/** Parameterized operations on the open project; no embedded diagram names or IDs. */
public final class Command {
    private static final Path ROOT = runtimeRoot();

    private static Path runtimeRoot() {
        try {
            // Command.class is loaded from <bridge root>/jobs by the plugin.
            return Paths.get(Command.class.getProtectionDomain().getCodeSource().getLocation().toURI()).getParent();
        } catch (java.net.URISyntaxException error) { throw new IllegalStateException(error); }
    }

    public static String run(ApplicationManager app) throws Exception {
        try { return execute(app); }
        catch (Exception error) {
            Throwable cause = error;
            while (cause.getCause() != null) cause = cause.getCause();
            return result("error", cause.toString());
        }
    }

    private static String execute(ApplicationManager app) throws Exception {
        Properties p = new Properties();
        try (java.io.Reader r = Files.newBufferedReader(ROOT.resolve("ipc/command.properties"), StandardCharsets.UTF_8)) { p.load(r); }
        IProject project = app.getProjectManager().getProject();
        if (project == null) throw new IllegalStateException("No project open");
        DiagramManager dm = app.getDiagramManager();
        String op = required(p, "operation");
        if ("save_project".equals(op)) {
            if (!app.getProjectManager().saveProject()) throw new IllegalStateException("Save failed");
            return "{\"saved\":true}";
        }
        if ("backup_project".equals(op)) {
            if (!app.getProjectManager().saveProject()) throw new IllegalStateException("Save failed; backup not created");
            if (project.getProjectFile() == null) throw new IllegalStateException("Project has no saved file");
            Path source = project.getProjectFile().toPath();
            if (!Files.isRegularFile(source)) throw new IllegalStateException("Saved project file not found");
            Path folder = ROOT.resolve("backups"); Files.createDirectories(folder);
            String stem = source.getFileName().toString().replaceFirst("(?i)\\.vpp$", "");
            Path backup = folder.resolve(stem + "-" + java.util.UUID.randomUUID() + ".vpp");
            Files.copy(source, backup); // No replacement: an existing backup must never be overwritten.
            return result("path", backup.toString());
        }
        if ("create_diagram".equals(op)) {
            IDiagramUIModel d = dm.createDiagram(required(p, "diagram_type"));
            d.setName(required(p, "name"));
            return result("diagram_id", d.getId());
        }
        IDiagramUIModel d = project.getDiagramById(required(p, "diagram_id"));
        if (d == null) throw new IllegalArgumentException("Diagram not found");
        switch (op) {
            case "create_element": {
                Method factory = factoryMethod(p, false);
                int[] b = bounds(p);
                IShapeUIModel parent = p.containsKey("parent_id") ? shape(d, p.getProperty("parent_id")) : null;
                IModelElement model = (IModelElement) factory.invoke(IModelElementFactory.instance());
                model.setName(p.getProperty("name", ""));
                IShapeUIModel s = (IShapeUIModel) dm.createDiagramElement(d, model);
                s.setBounds(b[0], b[1], b[2], b[3]);
                if (parent != null) {
                    parent.addChild(s);
                    if (parent.getModelElement() != null) parent.getModelElement().addChild(model);
                }
                s.resetCaption();
                return result("element_id", s.getId(), "model_id", model.getId());
            }
            case "rename_element": {
                IDiagramElement e = element(d, required(p, "element_id"));
                if (e.getModelElement() == null) throw new IllegalArgumentException("Element has no model");
                e.getModelElement().setName(required(p, "name")); e.resetCaption(); e.resetCaptionSize();
                return result("element_id", e.getId(), "model_id", e.getModelElement().getId());
            }
            case "set_bounds": {
                IShapeUIModel s = shape(d, required(p, "element_id"));
                int[] b = bounds(p); s.setBounds(b[0], b[1], b[2], b[3]); s.resetCaption(); s.resetCaptionSize();
                return result("element_id", s.getId());
            }
            case "get_connector": {
                return connectorDetails(connector(d, required(p, "element_id")));
            }
            case "set_object_type": {
                IDiagramElement e = element(d, required(p, "element_id"));
                if (!(e.getModelElement() instanceof IObjectNode)) throw new IllegalArgumentException("Expected ObjectNode");
                IObjectNode node = (IObjectNode)e.getModelElement();
                node.setType(required(p, "type_name")); e.resetCaption(); e.resetCaptionSize();
                return result("element_id", e.getId(), "type", node.getTypeAsText());
            }
            case "set_flow_guard": {
                IConnectorUIModel c = connector(d, required(p, "element_id"));
                IModelElement m = c.getModelElement();
                String guard = required(p, "guard");
                if (!(m instanceof IControlFlow) && !(m instanceof IActivityObjectFlow))
                    throw new IllegalArgumentException("Expected activity flow");
                if (m instanceof IControlFlow) ((IControlFlow)m).setGuard(guard);
                else ((IActivityObjectFlow)m).setGuard(guard);
                m.setName(null); c.resetCaption(); c.resetCaptionSize();
                return connectorDetails(c);
            }
            case "delete_disconnected_node": {
                IShapeUIModel s = shape(d, required(p, "element_id"));
                IModelElement m = s.getModelElement();
                if (m == null || m instanceof IRelationship)
                    throw new IllegalArgumentException("Expected node with model");
                if (m.getDiagramElements().length != 1 || m.childCount() != 0 || m.subDiagramCount() != 0)
                    throw new IllegalStateException("Shared or non-leaf node; deletion refused");
                if (m.fromRelationshipCount() + m.toRelationshipCount() + m.fromRelationshipEndCount()
                    + m.toRelationshipEndCount() + m.fromChartRelationshipCount() + m.toChartRelationshipCount() != 0)
                    throw new IllegalStateException("Node has relationships; disconnect first");
                String elementId = s.getId(), modelId = m.getId();
                m.delete();
                return result("element_id", elementId, "model_id", modelId);
            }
            case "set_connector_points": {
                IConnectorUIModel c = connector(d, required(p, "element_id"));
                Point[] points = points(required(p, "points"));
                if (points.length < 2) throw new IllegalArgumentException("At least two points required");
                c.clearPoints();
                for (Point point : points) c.addPoint(point);
                c.resetCaption(); c.resetCaptionSize();
                return connectorDetails(c);
            }
            case "set_connector_style": {
                IConnectorUIModel c = connector(d, required(p, "element_id"));
                String style = required(p, "style");
                int value;
                if ("rectilinear".equals(style)) value = IConnectorUIModel.CS_RECTI_LINEAR;
                else if ("oblique".equals(style)) value = IConnectorUIModel.CS_OBLIQUE;
                else throw new IllegalArgumentException("Unsupported connector style");
                c.setConnectorStyle(value);
                return connectorDetails(c);
            }
            case "set_connector_caption": {
                IConnectorUIModel c = connector(d, required(p, "element_id"));
                ICaptionUIModel caption = c.getCaptionUIModel();
                if (caption == null) throw new IllegalArgumentException("Connector has no caption");
                int[] b = bounds(p);
                caption.setBounds(b[0], b[1], b[2], b[3]);
                caption.setVisible(true);
                return connectorDetails(c);
            }
            case "delete_relationship": {
                IDiagramElement e = element(d, required(p, "element_id"));
                IModelElement model = e.getModelElement();
                if (!(e instanceof IConnectorUIModel) || !(model instanceof IRelationship))
                    throw new IllegalArgumentException("Only a connector backed by a relationship can be deleted");
                String elementId = e.getId(), modelId = model.getId();
                int views = 0;
                for (IDiagramUIModel diagram : project.toDiagramArray()) {
                    for (IDiagramElement view : diagram.toDiagramElementArray()) {
                        if (view.getModelElement() != null && modelId.equals(view.getModelElement().getId())) views++;
                    }
                }
                if (views != 1) throw new IllegalStateException("Relationship has " + views + " views; shared deletion refused");
                model.delete();
                return result("element_id", elementId, "model_id", modelId);
            }
            case "connect_elements": {
                Method factory = factoryMethod(p, true);
                IShapeUIModel from = shape(d, required(p, "from_id")), to = shape(d, required(p, "to_id"));
                if (from.getModelElement() == null || to.getModelElement() == null)
                    throw new IllegalArgumentException("Both endpoints need model elements");
                Point[] points = null;
                if (p.containsKey("points") && !p.getProperty("points").isEmpty()) {
                    points = points(p.getProperty("points"));
                }
                if (p.containsKey("condition")) {
                    Class<?> type = factory.getReturnType();
                    if (!IExtend.class.isAssignableFrom(type) && !IControlFlow.class.isAssignableFrom(type)
                        && !IActivityObjectFlow.class.isAssignableFrom(type))
                        throw new IllegalArgumentException("Condition requires Extend, ControlFlow, or ActivityObjectFlow");
                }
                IRelationship relation = (IRelationship) factory.invoke(IModelElementFactory.instance());
                relation.setFrom(from.getModelElement()); relation.setTo(to.getModelElement());
                if (p.containsKey("name")) relation.setName(p.getProperty("name"));
                if (p.containsKey("condition")) {
                    String value = p.getProperty("condition");
                    if (relation instanceof IExtend) ((IExtend) relation).setCondition(value);
                    if (relation instanceof IControlFlow) ((IControlFlow) relation).setGuard(value);
                    if (relation instanceof IActivityObjectFlow) ((IActivityObjectFlow) relation).setGuard(value);
                }
                IDiagramElement connector = dm.createConnector(d, relation, from, to, points);
                return result("element_id", connector.getId(), "model_id", relation.getId());
            }
            case "export_diagram": {
                String filename = required(p, "filename");
                if (!filename.matches("[A-Za-z0-9_-]+\\.png")) throw new IllegalArgumentException("Use a simple .png filename");
                Path folder = ROOT.resolve("exports"); Files.createDirectories(folder);
                Path path = folder.resolve(filename);
                if (Files.exists(path)) throw new IllegalArgumentException("Export exists; choose another filename");
                app.getModelConvertionManager().exportDiagramAsImage(d, path.toFile(), ModelConvertionManager.IMAGE_TYPE_PNG);
                if (!Files.isRegularFile(path)) throw new IllegalStateException("Export failed");
                return result("path", path.toString());
            }
            default: throw new IllegalArgumentException("Unknown operation: " + op);
        }
    }

    private static Method factoryMethod(Properties p, boolean relationship) throws Exception {
        String type = required(p, "model_type");
        if (!type.matches("[A-Z][A-Za-z0-9]+")) throw new IllegalArgumentException("Invalid model_type");
        Method method = IModelElementFactory.class.getMethod("create" + type);
        if (!IModelElement.class.isAssignableFrom(method.getReturnType())
            || IRelationship.class.isAssignableFrom(method.getReturnType()) != relationship)
            throw new IllegalArgumentException("Wrong node/relationship type");
        return method;
    }
    private static IDiagramElement element(IDiagramUIModel d, String id) {
        IDiagramElement e = d.getDiagramElementById(id);
        if (e == null) throw new IllegalArgumentException("Element not in diagram");
        return e;
    }
    private static IShapeUIModel shape(IDiagramUIModel d, String id) {
        IDiagramElement e = element(d, id);
        if (!(e instanceof IShapeUIModel)) throw new IllegalArgumentException("Expected shape");
        return (IShapeUIModel)e;
    }
    private static IConnectorUIModel connector(IDiagramUIModel d, String id) {
        IDiagramElement e = element(d, id);
        if (!(e instanceof IConnectorUIModel)) throw new IllegalArgumentException("Expected connector");
        return (IConnectorUIModel)e;
    }
    private static Point[] points(String value) {
        String[] pairs = value.split(";", -1);
        Point[] points = new Point[pairs.length];
        for (int i = 0; i < pairs.length; i++) {
            String[] xy = pairs[i].split(",", -1);
            if (xy.length != 2) throw new IllegalArgumentException("Invalid point");
            points[i] = new Point(Integer.parseInt(xy[0]), Integer.parseInt(xy[1]));
        }
        return points;
    }
    private static String connectorDetails(IConnectorUIModel c) {
        StringBuilder b = new StringBuilder("{\"element_id\":").append(q(c.getId()))
            .append(",\"model_id\":").append(c.getModelElement() == null ? "null" : q(c.getModelElement().getId()))
            .append(",\"from_id\":").append(c.getFromShape() == null ? "null" : q(c.getFromShape().getId()))
            .append(",\"to_id\":").append(c.getToShape() == null ? "null" : q(c.getToShape().getId()))
            .append(",\"guard\":").append(flowGuard(c.getModelElement()))
            .append(",\"connector_style\":").append(c.getConnectorStyle())
            .append(",\"bounds\":[").append(c.getX()).append(',').append(c.getY()).append(',')
            .append(c.getWidth()).append(',').append(c.getHeight()).append(']')
            .append(",\"points\":[");
        Point[] points = c.getPoints();
        if (points != null) for (int i = 0; i < points.length; i++) {
            if (i != 0) b.append(',');
            b.append('[').append(points[i].x).append(',').append(points[i].y).append(']');
        }
        b.append("],\"caption\":");
        ICaptionUIModel caption = c.getCaptionUIModel();
        if (caption == null) b.append("null");
        else b.append("{\"visible\":").append(caption.isVisible()).append(",\"bounds\":[")
            .append(caption.getX()).append(',').append(caption.getY()).append(',')
            .append(caption.getWidth()).append(',').append(caption.getHeight()).append("]}");
        return b.append('}').toString();
    }
    private static String flowGuard(IModelElement model) {
        String guard = model instanceof IControlFlow ? ((IControlFlow)model).getGuard()
            : model instanceof IActivityObjectFlow ? ((IActivityObjectFlow)model).getGuard() : null;
        return guard == null ? "null" : q(guard);
    }
    private static int[] bounds(Properties p) {
        int[] b = {Integer.parseInt(required(p,"x")), Integer.parseInt(required(p,"y")),
            Integer.parseInt(required(p,"width")), Integer.parseInt(required(p,"height"))};
        if (b[2] <= 0 || b[3] <= 0) throw new IllegalArgumentException("Size must be positive");
        return b;
    }
    private static String required(Properties p, String key) {
        String value = p.getProperty(key);
        if (value == null || value.isEmpty()) throw new IllegalArgumentException("Missing " + key);
        return value;
    }
    private static String result(String... fields) {
        StringBuilder b = new StringBuilder("{");
        for (int i = 0; i < fields.length; i += 2) {
            if (i != 0) b.append(',');
            b.append(q(fields[i])).append(':').append(q(fields[i+1]));
        }
        return b.append('}').toString();
    }
    private static String q(String text) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : text.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 32) b.append(String.format("\\u%04x", (int)c));
            else b.append(c);
        }
        return b.append('"').toString();
    }
}
