"""Visual reconstruction of PSILO. Only 920 x 760 x 680 overall is published.
All other geometry is estimated from photos, not manufacturing CAD.
Run Blender in background with this script to export GLB and a native scene.
"""
import bpy, math, os
from mathutils import Vector
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
S=.001
# Millimetres; all estimates except overall dimensions.
P={'width':920,'depth':760,'height':680,'plate_depth':585,'plate_width':710,
   'base_level':100,'seat_level':327,'arm_under':572,'timber_w':130,
   'timber_h':108,'arm_length':650,'bend_radius':16,'sheet_thickness':5}

def material(name,col,metal=0,rough=.5):
 m=bpy.data.materials.new(name);m.diffuse_color=(*col,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*col,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 if metal==0: p.inputs['Specular IOR Level'].default_value=.1
 return m
metal=material('Satin aluminium',(.55,.57,.58),.88,.31)
wood=material('Black stained walnut',(.004,.0038,.0036),0,.75)
leather=material('Black leather',(.006,.006,.006),0,.72)
screwmat=material('Fastener',(.38,.40,.41),.9,.26)

def roundbox(name,loc,dims,mat,r):
 bpy.ops.mesh.primitive_cube_add(size=1,location=tuple(v*S for v in loc));o=bpy.context.object;o.name=name
 o.dimensions=tuple(v*S for v in dims);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 m=o.modifiers.new('Rounded edges','BEVEL');m.width=r*S;m.segments=6
 m=o.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL')
 o.data.materials.append(mat);return o

def rounded_path(points,radius,steps=8):
 out=[Vector(points[0])]
 for i in range(1,len(points)-1):
  prev,cur,nxt=(Vector(points[j]) for j in (i-1,i,i+1)); a=(prev-cur).normalized();b=(nxt-cur).normalized();angle=a.angle(b)
  d=min(radius/math.tan(angle/2), (prev-cur).length*.45,(nxt-cur).length*.45)
  start=cur+a*d;end=cur+b*d
  # quadratic sampled curve approximates smooth sheet bend
  for k in range(steps+1):
   t=k/steps;out.append((1-t)**2*start+2*(1-t)*t*cur+t*t*end)
 out.append(Vector(points[-1]));return out

def folded(name,points,depth,thickness=5):
 path=rounded_path(points,P['bend_radius']);n=len(path)
 verts=[(v.x*S,y*S,v.y*S) for y in (-depth/2,depth/2) for v in path]
 faces=[(i,i+1,n+i+1,n+i) for i in range(n-1)]
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
 o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(metal)
 for face in mesh.polygons:face.use_smooth=True
 m=o.modifiers.new('Indicative sheet thickness','SOLIDIFY');m.thickness=thickness*S;m.offset=0
 m=o.modifiers.new('Soft edges of sheet','BEVEL');m.width=.002;m.segments=3
 m=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');return o

# Two broad, continuous folded sheets, meeting at the platform below the seat.
folded('Upper continuous U-shaped sheet',[(-355,572),(-355,329),(355,329),(355,572)],P['plate_depth'])
folded('Lower continuous folded sheet',[(-445,100),(-355,100),(-355,321),(355,321),(355,100),(445,100)],P['plate_depth'])
# Four long solid timber beams, bevels and proportions approximated visually.
for side, label in [(-1,'Left'),(1,'Right')]:
 roundbox(label+' foot timber',(side*395,0,50),(130,760,100),wood,12)
 roundbox(label+' arm timber',(side*395,-20,626),(130,650,108),wood,14)
 # Representative visible flush fasteners: actual fixings unknown.
 for yy in (-245,245):
  for xx in (side*378,side*421):
   bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.006,depth=.0015,location=(xx*S,yy*S,.1035));o=bpy.context.object;o.name=label+' indicative fastener';o.data.materials.append(screwmat)
# Seat cushion is slightly inset with generous radius and a thin visual seam.
roundbox('Seat cushion',(0,-10,357),(670,545,52),leather,22)
# Backrest panel: slight backward lean, a continuous narrow metal rim around upholstery.
back=roundbox('Backrest aluminium panel',(0,266,560),(660,6,235),metal,11)
back.rotation_euler.x=math.radians(-10)
pad=roundbox('Backrest leather',(0,251,562),(620,38,200),leather,18)
pad.rotation_euler.x=math.radians(-10)
# S-shaped strips from back panel toward arm beams, in plan view, rounded bends.
def bracket(side):
 path=rounded_path([(side*321,267),(side*344,267),(side*344,211),(side*340,211)],14,8);n=len(path)
 verts=[(v.x*S,v.y*S,z*S) for z in (505,594) for v in path]
 faces=[(i,i+1,n+i+1,n+i) for i in range(n-1)]
 me=bpy.data.meshes.new('Bent rear connector');me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(('Left' if side<0 else 'Right')+' bent rear connector',me);bpy.context.collection.objects.link(o);o.data.materials.append(metal)
 for f in me.polygons:f.use_smooth=True
 m=o.modifiers.new('Thickness','SOLIDIFY');m.thickness=.005;m.offset=0
 m=o.modifiers.new('Edge rounding','BEVEL');m.width=.002;m.segments=3
 o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
for side in (-1,1):bracket(side)
# Save/export only the chair, then add a separate presentation scene for QA.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'psilo-concept.blend'))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,'psilo-concept.glb'),export_format='GLB')
# Neutral studio for checking the model from the reference angle.
floor=material('Studio floor',(.19,.20,.20),.15,.5)
roundbox('Studio floor',(0,0,-12),(5000,5000,20),floor,0)
world=bpy.context.scene.world;world.color=(.23,.23,.23)
def area(name,xyz,power,size,target):
 bpy.ops.object.light_add(type='AREA',location=xyz);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Key',(-2,-3,4),150,4,(0,0,.3));area('Rim',(2,2,3),220,3,(0,0,.35));area('Fill',(1,-4,2),100,3,(0,0,.35))
bpy.ops.object.camera_add(location=(-1.7,-2.55,1.9));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.33))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.8
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=32
scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=os.path.join(OUT,'reference-view.png');bpy.ops.render.render(write_still=True)
