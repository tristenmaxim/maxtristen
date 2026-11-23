"""PSILO-inspired study, millimetres. NOT approved for cutting or use.
Run with FreeCAD's bundled Python and PYTHONPATH=FreeCAD Resources/lib.
Generates coherent bent solids and theoretical neutral-axis blanks; must adjust
material / tooling / bend compensation after shop trial. Back connection open.
"""
import os, math, json, csv
import FreeCAD as App, Part
from FreeCAD import Vector
out=os.path.dirname(os.path.abspath(__file__))
D=580.; T=5.; R=10.; K=.4; BA=math.pi/2*(R+K*T)
# rectangular rectangular blocks, x/y/z in mm
box=lambda x,y,z,dx,dy,dz: Part.makeBox(dx,dy,dz,Vector(x,y,z))
def quarter(cx,cz,sx,sz):
    # annular bend swept along Y; bounding region picks requested quadrant
    outer=Part.makeCylinder(R+T,D,Vector(cx,-D/2,cz),Vector(0,1,0))
    inner=Part.makeCylinder(R,D,Vector(cx,-D/2,cz),Vector(0,1,0))
    return outer.cut(inner).common(box(cx if sx>0 else cx-R-T,-D/2,cz if sz>0 else cz-R-T,R+T,D,R+T))
def merge(shapes):
    s=shapes[0]
    for x in shapes[1:]:s=s.fuse(x)
    return s.removeSplitter()
def drilled(shape,holes):
    for x,y,z in holes:shape=shape.cut(Part.makeCylinder(3.25,12,Vector(x,y,z),Vector(0,0,1)))
    return shape.removeSplitter()
# Upper U: outside width 710, z bottom 330, side top 580.
upper=merge([box(-340,-290,330,680,D,T),box(350,-290,345,T,D,235),box(-355,-290,345,T,D,235),quarter(340,345,1,-1),quarter(-340,345,-1,-1)])
# Lower U: continuous platform in contact with upper underside, feet outside.
lower=merge([box(-340,-290,325,680,D,T),box(350,-290,115,T,D,200),box(-355,-290,115,T,D,200),box(365,-290,100,80,D,T),box(-445,-290,100,80,D,T),quarter(340,315,1,1),quarter(-340,315,-1,1),quarter(365,115,-1,-1),quarter(-365,115,1,-1)])
central=[(x,y) for x in (-250,250) for y in (-200,200)]
upper=drilled(upper,[(x,y,326) for x,y in central]);lower=drilled(lower,[(x,y,324) for x,y in central]+[(x,y,98) for x in (-400,400) for y in (-220,220)])
doc=App.newDocument('PSILO_Study'); objects=[]
def feature(name,shape):
    obj=doc.addObject('PartDesign::Feature',name);obj.Shape=shape;objects.append(obj);return obj
feature('Upper_sheet_5mm',upper);feature('Lower_sheet_5mm',lower)
for sign,name in [(-1,'Left'),(1,'Right')]:
    xx=-460 if sign==-1 else 330
    beam=box(xx,-380,0,130,760,100)
    # Pilot blind holes in wood are intentionally NOT included: fitting unapproved.
    feature(name+'_base_wood',beam)
    feature(name+'_arm_wood',box(xx,-325,580,130,650,100))
# non-structural placeholders, shown to engineer; no unsupported assembly claim
feature('Seat_pad_placeholder',box(-330,-275,335,660,540,52))
feature('Back_panel_unconnected',box(-330,280,445,660,5,230))
feature('Back_pad_placeholder',box(-310,241,460,620,39,200))
doc.recompute();doc.saveAs(os.path.join(out,'psilo-study.FCStd'))
Part.export(objects,os.path.join(out,'psilo-study.step'))
# ASCII DXF R12 in millimetres, closed outline CUT and bend centres BEND_REFERENCE.
def dxf(name,length,bend_positions,holes):
    code=['0','SECTION','2','HEADER','9','$INSUNITS','70','4','0','ENDSEC','0','SECTION','2','ENTITIES']
    def line(layer,x1,y1,x2,y2):
      code.extend(['0','LINE','8',layer,'10',str(x1),'20',str(y1),'30','0','11',str(x2),'21',str(y2),'31','0'])
    def circle(x,y):code.extend(['0','CIRCLE','8','CUT','10',f'{x:.6f}','20',str(y),'30','0','40','3.25'])
    for x1,y1,x2,y2 in [(0,0,length,0),(length,0,length,D),(length,D,0,D),(0,D,0,0)]:line('CUT',round(x1,6),y1,round(x2,6),y2)
    for x in bend_positions:line('BEND_REFERENCE',round(x,6),0,round(x,6),D)
    for x,y in holes:circle(x,y)
    code+=['0','ENDSEC','0','EOF']
    with open(os.path.join(out,name),'w') as f:f.write('\n'.join(code)+'\n')
U=235*2+680+2*BA; L=80*2+200*2+680+4*BA
ub=[235+BA/2,235+1.5*BA+680]
lb=[80+BA/2,80+1.5*BA+200,80+2.5*BA+200+680,80+3.5*BA+400+680]
dxf('upper-study.dxf',U,ub,[(U/2+x,290+y) for x,y in central])
dxf('lower-study.dxf',L,lb,[(L/2+x,290+y) for x,y in central]+[(x,y) for x in (45,L-45) for y in (70,510)])
# measured geometry validation; do not mistake for a structural check
for name,s in [('upper',upper),('lower',lower)]:
    if not s.isValid() or len(s.Solids)!=1:raise RuntimeError('Invalid / disconnected '+name)
contact=upper.common(lower)
if contact.Volume>1e-5:raise RuntimeError('Unexpected metal interference')
report={'units':'mm','sheet_thickness':T,'inside_radius':R,'k_factor_assumed':K,'bend_allowance_per_90':BA,'upper_blank_length':U,'lower_blank_length':L,'blank_depth':D,'upper_bend_centres':ub,'lower_bend_centres':lb,'coincident_plate_holes':central,'foot_holes':[(-400,-220),(-400,220),(400,-220),(400,220)],'upper_valid':upper.isValid(),'lower_valid':lower.isValid(),'upper_solids':len(upper.Solids),'lower_solids':len(lower.Solids),'overlap_volume_mm3':contact.Volume,'caution':'PRELIMINARY ONLY; bend compensation, alloys, fasteners, back support and structural integrity NOT confirmed'}
with open(os.path.join(out,'validation.json'),'w') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
