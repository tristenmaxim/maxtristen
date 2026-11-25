import bpy, math, os
from mathutils import Vector
root=os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(root,'psilo-concept.blend'))
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=72
scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='JPEG';scene.render.image_settings.quality=94
scene.world.color=(.23,.23,.23)
# Diffuse floor catches soft shadows; neutral studio leaves the silhouette legible.
m=bpy.data.materials.new('Studio floor');m.diffuse_color=(.21,.22,.22,1);m.use_nodes=True
m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.55
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.002));bpy.context.object.data.materials.append(m)
def area(pos,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area((-2,-3,4),150,4,(0,0,.3));area((2,2,3),220,3,(0,0,.35));area((1,-4,2),100,3,(0,0,.35))
bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.lens=50
out=os.path.join(root,'../renders');os.makedirs(out,exist_ok=True)
views=[('01-general',(-1.8,-2.7,1.8),(0,0,.34),1.65),('02-side',(-3,-.20,1.05),(0,0,.34),1.42),('03-detail',(-1.45,-2.0,1.58),(-.25,-.06,.52),.78)]
for name,pos,target,scale in views:
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
 scene.render.filepath=os.path.join(out,name+'.jpg');bpy.ops.render.render(write_still=True)
