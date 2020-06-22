import pymel.core as pm
import maya.api.OpenMaya as om2

from silhouettepolisher.selection import (
    selection_required, filter_selection, selection_contains_at_least,
    select_shape_transforms, filter_transforms_by_children_types,
    selection_contains_exactly, preserve_selection)


CORRECTIVE_BLENDSHAPE_NAME = 'corrective_blendshape'
CORRECTIVE_BLENDSHAPE_ATTR = 'is_corrective_blendshape'

WORKING_MESH_ATTR = 'is_working_copy_mesh'
DISPLAY_MESH_ATTR = 'is_display_copy_mesh'
TARGET_MESH_ATTR = 'is_a_target_edit'
BLENDSHAPE_EDIT_ATTR = 'is_blendshape_edit'

WORKING_MESH_SHADER = 'TMP_WORKING_COPY_BLINN'
WORKING_MESH_SG = 'TMP_WORKING_COPY_BLINNSG'
DISPLAY_MESH_SHADER = 'TMP_DISPLAY_COPY_LAMBERT'
DISPLAY_MESH_SG = 'TMP_DISPLAY_COPY_LAMBERTSG'


@filter_selection(type=('mesh', 'transform'), objectsOnly=True)
@select_shape_transforms
@filter_transforms_by_children_types('mesh')
@selection_contains_at_least(1, 'transform')
@selection_required
def create_working_copy_on_selection():
    for transform in pm.ls(selection=True):
        if mesh_has_working_copy(transform):
            continue
        if transform.hasAttr(WORKING_MESH_ATTR):
            continue
        if transform.hasAttr(DISPLAY_MESH_ATTR):
            continue
        setup_working_copy(transform)
    pm.mel.eval('SculptGeometryToolOptions')


def setup_working_copy(mesh, working_copy=None, display_copy=None):
    """
    this function setup the working editing environment.
    the working copy and the display copy are temporary meshes used
    to make and previzualize the mesh edit.
    if working_copy and display_copy are let as None, the function will duplicate
    the specified one.

    the original mesh is hidden during the procedure (lodVisibility)
    the working copy, is a mesh for create the deformation.
    the display copy, is a copy (hidden by default), to compare the working
    copy to the original mesh.

    a red shader is assigned to the working copy
    a blue shader is assigned to the display copy
    """
    original_mesh = pm.PyNode(mesh)
    working_copy = pm.PyNode(working_copy) if working_copy else original_mesh.duplicate()[0]
    display_copy = pm.PyNode(display_copy) if display_copy else original_mesh.duplicate()[0]

    # clean intermediate duplicated shapes
    for shape in working_copy.getShapes() + display_copy.getShapes():
        if shape.intermediateObject.get() is True:
            pm.delete(shape)

    original_mesh.lodVisibility.set(False)
    working_copy.rename(working_copy.name() + '_f' + str(pm.env.time))
    for shape in display_copy.getShapes():
	ensure_node_disconnected(shape)
        shape.overrideEnabled.set(True)
        shape.overrideDisplayType.set(2)

    # create and link attibutes to connect working meshes to original mesh.
    pm.addAttr(
        working_copy,
        attributeType='message',
        longName=WORKING_MESH_ATTR,
        niceName=WORKING_MESH_ATTR.replace('_', ' '))

    pm.addAttr(
        display_copy,
        attributeType='message',
        longName=DISPLAY_MESH_ATTR,
        niceName=DISPLAY_MESH_ATTR.replace('_', ' '))

    original_mesh.message >> working_copy.is_working_copy_mesh
    original_mesh.message >> display_copy.is_display_copy_mesh

    # create shaders
    if not pm.objExists(WORKING_MESH_SHADER):
        pm.shadingNode('blinn', asShader=True, name=WORKING_MESH_SHADER)
    working_copy_shader = pm.PyNode(WORKING_MESH_SHADER)
    working_copy_shader.color.set(1, .25, .33)
    working_copy_shader.transparency.set(0, 0, 0)

    if not pm.objExists(DISPLAY_MESH_SHADER):
        pm.shadingNode('lambert', asShader=True, name=DISPLAY_MESH_SHADER)
    display_copy_shader = pm.PyNode(DISPLAY_MESH_SHADER)
    display_copy_shader.color.set(0, .25, 1)
    display_copy_shader.transparency.set(1, 1, 1)

    pm.select(working_copy)
    pm.hyperShade(working_copy, assign=working_copy_shader)
    pm.select(display_copy)
    pm.hyperShade(display_copy, assign=display_copy_shader)

    pm.select(working_copy)


def setup_edit_target_working_copy(mesh, blendshape, target_index):
    '''
    this function setup the working editing environment to edit an target.
    To get a working copy of the mesh, it force the blendshape envelope to 1
    and the selected target to 1. To generate the display copy it set the
    target value to 0.0.

    When the working setup is done, the envelope and target's original values
    are set back.

    on the working mesh an attribute "is_a_target_edit" and the edited index
    is stored as value. The blendshape message is connected to the
    working copy message. This is useful for the applying procedure. To notify
    that's an target edit instead of a target creation, an know which
    blendshape target is modified.
    '''
    original_mesh = pm.PyNode(mesh)
    original_target_value = blendshape.weight[target_index].get()
    original_envelope_value = blendshape.envelope.get()

    blendshape.envelope.set(1.0)

    pm.blendShape(blendshape, edit=True, weight=(target_index, 1.0))
    working_copy = original_mesh.duplicate()[0]

    pm.blendShape(blendshape, edit=True, weight=(target_index, 0.0))
    display_copy = original_mesh.duplicate()[0]

    setup_working_copy(original_mesh, working_copy, display_copy)

    pm.addAttr(
        working_copy,
        attributeType='byte',
        longName=TARGET_MESH_ATTR,
        niceName=TARGET_MESH_ATTR.replace('_', ' '))

    pm.addAttr(
        working_copy,
        attributeType='message',
        longName=BLENDSHAPE_EDIT_ATTR,
        niceName=BLENDSHAPE_EDIT_ATTR.replace('_', ' '))

    working_copy.attr(TARGET_MESH_ATTR).set(target_index)
    blendshape.message >> working_copy.attr(BLENDSHAPE_EDIT_ATTR)

    blendshape.envelope.set(original_envelope_value)
    pm.blendShape(
        blendshape, edit=True, weight=(target_index, original_target_value))


@filter_selection(type=('mesh', 'transform'), objectsOnly=True)
@select_shape_transforms
@filter_transforms_by_children_types('mesh')
@selection_contains_at_least(1, 'transform')
@selection_required
def delete_selected_working_copys():
    for mesh_transform in pm.ls(selection=True):
        if not mesh_transform.hasAttr(WORKING_MESH_ATTR):
            continue
        mesh = mesh_transform.attr(WORKING_MESH_ATTR).listConnections()[0]
        delete_working_copy_on_mesh(mesh)


def delete_working_copy_on_mesh(mesh):
    '''
    This function let the user cancel his work and delete current working copy
    '''
    original_mesh = pm.PyNode(mesh)
    working_meshes = [
        node for node in original_mesh.message.listConnections()
        if node.hasAttr(WORKING_MESH_ATTR) or node.hasAttr(DISPLAY_MESH_ATTR)]

    original_mesh.lodVisibility.set(True)
    pm.delete(working_meshes)

    # clean shaders
    if not pm.objExists(WORKING_MESH_SG):
        working_copy_shader_group = pm.PyNode(WORKING_MESH_SG)
        if not working_copy_shader_group.dagSetMembers.listConnections():
            pm.delete([WORKING_MESH_SG, WORKING_MESH_SHADER])

    if not pm.objExists(DISPLAY_MESH_SG):
        display_copy_shader_group = pm.PyNode(DISPLAY_MESH_SG)
        if not display_copy_shader_group.dagSetMembers.listConnections():
            pm.delete([DISPLAY_MESH_SG, DISPLAY_MESH_SHADER])


def get_working_copys_transparency():
    """
    this function's querying the working shaders transparency
    """
    if not pm.objExists(WORKING_MESH_SHADER):
        return 0.0
    if not pm.objExists(DISPLAY_MESH_SHADER):
        return 0.0
    working_copy_shader = pm.PyNode(WORKING_MESH_SHADER)
    return working_copy_shader.transparency.get()[0]


def set_working_copys_transparency(value):
    """
    this function's tweaking the working shaders to let user
    compare working mesh and original mesh
    """
    if not pm.objExists(WORKING_MESH_SHADER):
        return pm.warning('working mesh shader not found')
    if not pm.objExists(DISPLAY_MESH_SHADER):
        return pm.warning('working mesh shader not found')

    working_copy_shader = pm.PyNode(WORKING_MESH_SHADER)
    display_copy_shader = pm.PyNode(DISPLAY_MESH_SHADER)

    working_copy_shader.transparency.set(value, value, value)
    display_copy_shader.transparency.set(1 - value, 1 - value, 1 - value)


def get_corrective_blendshapes(mesh):
    """
    this function return a list off all corrective blendshapes
    present in the history
    """
    original_mesh = pm.PyNode(mesh)
    # retrieve the blendhspae connected to message combined to a listHistory.
    # This is to keep the history order, but be sure the blendshape is
    # from the good mesh in complexe setup
    # (there's probably smarter way to get this info ...)
    blendshape_connected = original_mesh.message.listConnections()
    return [
        node for node in original_mesh.inMesh.listHistory()
        if isinstance(node, pm.nt.BlendShape) and
        node.hasAttr(CORRECTIVE_BLENDSHAPE_ATTR) and
        node in blendshape_connected]


@filter_selection(type=('mesh', 'transform'), objectsOnly=True)
@select_shape_transforms
@filter_transforms_by_children_types('mesh')
@selection_contains_at_least(1, 'transform')
@selection_required
def create_blendshape_corrective_for_selected_working_copys(values=None):
    result = []
    for working_copy in pm.ls(selection=True):
        if not working_copy.hasAttr(WORKING_MESH_ATTR):
            continue
        original_mesh = working_copy.attr(WORKING_MESH_ATTR).listConnections()[0]
        create_blendshape_corrective_on_mesh(
            base=original_mesh, target=working_copy, values=values)
        delete_working_copy_on_mesh(original_mesh)
        result.append(original_mesh)
    if result:
        pm.select(result)


def create_blendshape_corrective_on_mesh(base, target, values=None):
    """
    this function's creating a new corrective blendshape on a mesh and add the
    first target
    """
    base = pm.PyNode(base)
    target = pm.PyNode(target)
    name = base.name() + '_' + CORRECTIVE_BLENDSHAPE_NAME

    corrective_blendshape = pm.blendShape(
        target, base, name=name, before=True, weight=(0, 1))[0]

    pm.addAttr(
        corrective_blendshape, attributeType='message',
        longName=CORRECTIVE_BLENDSHAPE_ATTR,
        niceName=CORRECTIVE_BLENDSHAPE_ATTR.replace('_', ' '))

    base.message >> corrective_blendshape.attr(CORRECTIVE_BLENDSHAPE_ATTR)

    if values is not None:
        apply_animation_template_on_blendshape_target_weight(
            blendshape=corrective_blendshape, target_index=0, values=values)


def mesh_has_working_copy(mesh):
    '''
    This function query if a working copy is currently in use
    it should never append
    '''
    return bool([
        node for node in mesh.message.listConnections()
        if node.hasAttr(WORKING_MESH_ATTR) or node.hasAttr(DISPLAY_MESH_ATTR)])


def add_target_on_corrective_blendshape(blendshape, target, base, values=None):
    '''
    this is a simple function to add target on a blendshape
    '''

    corrective_blendshape = pm.PyNode(blendshape)
    base = pm.PyNode(base)
    target = pm.PyNode(target)

    index = int(
        corrective_blendshape.inputTarget[0].inputTargetGroup.get(
            multiIndices=True)[-1] + 1)

    set_target_relative(corrective_blendshape, target, base)
    target.outMesh.get(type=True)

    # the target is created with "1.0" as weight. But it still created with
    # value set to 0.0. If the value is not set to 1.0, strange bug's appears
    # I have to set the target after if I want my value to 1.0 (life's strange)
    pm.blendShape(
        corrective_blendshape, edit=True, before=True,
        target=(base, index, target, 1.0))
    pm.blendShape(corrective_blendshape, edit=True, weight=(index, 1.0))

    apply_animation_template_on_blendshape_target_weight(
        blendshape=corrective_blendshape, target_index=index, values=values)


def apply_edit_target_working_copy(working_copy):
    """
    this function apply a target edit.
    To do that, it retrieve information about the setup from the working copy.
    Set the blendshapetarget to 0.0 and use the display copy to to calculate
    the relative target mesh.
    Connect the working mesh to the correct blendshape input target to update
    it.
    Put back the target value to his original value to clean the scene.
    """
    working_copy = pm.PyNode(working_copy)
    original_mesh = working_copy.attr(WORKING_MESH_ATTR).listConnections()[0]
    display_copy = [
        node for node in original_mesh.message.listConnections()
        if node.hasAttr(DISPLAY_MESH_ATTR)][0]

    blendshape = working_copy.attr(BLENDSHAPE_EDIT_ATTR).listConnections()[0]
    target_index = int(working_copy.attr(TARGET_MESH_ATTR).get())
    target_original_value = blendshape.weight[target_index].get()
    blendshape_input = (
        blendshape.inputTarget[target_index].inputTargetGroup[0].
        inputTargetItem[6000].inputGeomTarget)  # ok it's a long path :)

    blendshape.weight[target_index].set(0)
    set_target_relative(blendshape, working_copy, display_copy)
    working_copy.worldMesh[0] >> blendshape_input

    blendshape.weight[target_index].set(target_original_value)


@filter_selection(type=('mesh', 'transform'), objectsOnly=True)
@select_shape_transforms
@selection_contains_at_least(1, 'transform')
@selection_required
def apply_selected_working_copys(values=None):
    result = []
    for worky_copy in pm.ls(selection=True):
        if worky_copy.hasAttr(WORKING_MESH_ATTR):
            result.append(apply_working_copy(worky_copy, values=values))
    if result:
        pm.select(result)


def apply_working_copy(mesh, blendshape=None, values=None):
    '''
    this function is let apply a working mesh on his main shape
    it manage if a blendshape already exist or not.
    '''
    working_mesh = pm.PyNode(mesh)
    if not working_mesh.hasAttr(WORKING_MESH_ATTR):
        pm.warning('please, select working mesh')

    original_mesh = working_mesh.attr(
        WORKING_MESH_ATTR).listConnections()[0]

    if working_mesh.hasAttr(TARGET_MESH_ATTR):
        apply_edit_target_working_copy(working_mesh)

    elif blendshape:
        add_target_on_corrective_blendshape(
            blendshape, working_mesh, original_mesh, values=values)

    elif blendshape is None:
        blendshapes = get_corrective_blendshapes(original_mesh)
        if not blendshapes:
            create_blendshape_corrective_on_mesh(
                original_mesh, working_mesh, values=values)
        else:
            add_target_on_corrective_blendshape(
                blendshapes[0], working_mesh, original_mesh, values=values)

    delete_working_copy_on_mesh(original_mesh)
    return original_mesh


@filter_selection(type=('mesh', 'transform'), objectsOnly=True)
@select_shape_transforms
@selection_contains_exactly(1, 'transform')
def get_targets_list_from_selection():
    original_mesh = pm.ls(selection=True)[0]
    return original_mesh, get_targets_list_from_mesh(original_mesh)


def get_targets_list_from_mesh(mesh):
    '''
    this function return a list tuple containing the blendshape corrective
    connected and the target available per blendshapes
    '''
    mesh = pm.PyNode(mesh)
    blendshapes = get_corrective_blendshapes(mesh)
    if not blendshapes:
        return None
    return [(bs, pm.listAttr(bs.w, multi=True)) for bs in blendshapes]


def set_target_relative(blendshape, target, base):
    """
    the function is setting the target relative to the base if a blendshape
    exist to avoid double transformation when the target is applyied
    Thanks Carlo Giesa, this one is yours :)
    """
    target = pm.PyNode(target)
    base = pm.PyNode(base)

    blendshape = pm.PyNode(blendshape)
    intermediate = pm.createNode('mesh')
    in_mesh = blendshape.input[0].inputGeometry.listConnections(plugs=True)[0]
    in_mesh >> intermediate.inMesh
    intermediate.outMesh.get(type=True)  # this force mesh evaluation
    in_mesh // intermediate.inMesh

    selection_list = om2.MSelectionList()
    selection_list.add(target.name())
    selection_list.add(base.name())
    selection_list.add(intermediate.name())

    target_fn_mesh = om2.MFnMesh(selection_list.getDagPath(0))
    target_points = target_fn_mesh.getPoints()
    base_points = om2.MFnMesh(selection_list.getDagPath(1)).getPoints()
    intermediate_points = om2.MFnMesh(selection_list.getDagPath(2)).getPoints()
    selection_list.clear()

    i = 0
    while (i < len(target_points)):
        intermediate_points[i] = (
            intermediate_points[i] + (target_points[i] - base_points[i]))
        i += 1

    target_fn_mesh.setPoints(intermediate_points)
    target_fn_mesh.updateSurface()
    pm.delete(intermediate.getParent())


def ensure_node_disconnected(node):
   """
   This function clean all plug from a node
   """
   for inplug, outplug in node.listConnections(plugs=True, connections=True):
       try:
           outplug.disconnect(inplug)
       # That the lazy way, if disconnection fail, that because inplug and outplug
       # are reversed ...
       except RuntimeError:
           inplug.disconnect(outplug)


def apply_animation_template_on_blendshape_target_weight(
        blendshape, target_index, values=None):
    """
    this function will apply an animation on the blendshape target index given.
    the value is an float array. It represent a value at frame.
    the array middle value is the value set at the current frame.
    """
    if values is None or not any(1 for v in values if v is not None):
        return

    blendshape = pm.PyNode(blendshape)
    startframe = int(pm.env.time - float(len(values) / 2) + .5)
    endframe = int(pm.env.time + float(len(values) / 2) + .5)
    frames = range(int(startframe), int(endframe))
    decimal = pm.env.time - int(pm.env.time)
    frames_values = {
        f + decimal: values[i] for i, f in enumerate(frames)
        if values[i] is not None}

    for frame, value in frames_values.iteritems():
        pm.setKeyframe(
            blendshape.weight[target_index], time=frame, value=value,
            inTangentType='linear', outTangentType='linear')

    # this force maya to refresh the current frame in evaluation
    # without those lines, maya does'nt refresh the current frame if a
    # key is set at this timing.
    if frames_values.get(pm.env.time) is not None:
        pm.blendShape(
            blendshape, edit=True,
            weight=(target_index, frames_values[pm.env.time]))
