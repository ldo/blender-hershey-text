#+
# This addon for Blender 2.7 uses the Hershey fonts to turn a text
# object into a collection of curves. Also needs HersheyPy
# <https://github.com/ldo/hersheypy> to be installed.
#
# Copyright 2015 Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#-

import math
import sys # debug
import os
import bpy
import mathutils
import hershey_font

bl_info = \
    {
        "name" : "Hershey Text",
        "author" : "Lawrence D'Oliveiro <ldo@geek-central.gen.nz>",
        "version" : (0, 1, 0),
        "blender" : (2, 7, 5),
        "location" : "View 3D > Object Mode > Tool Shelf",
        "description" :
            "Uses a Hershey font to turn a text object into a collection of curves.",
        "warning" : "",
        "wiki_url" : "",
        "tracker_url" : "",
        "category" : "Object",
    }

class Failure(Exception) :

    def __init__(self, msg) :
        self.msg = msg
    #end __init__

#end Failure

def list_hershey_fonts() :
    result = [(" ", "(pick a font)", "")]
    for item in os.listdir(hershey_font.default_path) :
        if item.endswith(hershey_font.default_ext) :
            item = item[: - len(hershey_font.default_ext)]
            result.append \
              (
                (item, item, "")
              )
        #end if
    #end for
    return \
        result
#end list_hershey_fonts

class HersheyText(bpy.types.Operator) :
    bl_idname = "text.hersheyfy"
    bl_label = "Hershey Text"
    bl_context = "objectmode"
    bl_options = {"REGISTER", "UNDO"}

    font_name = bpy.props.EnumProperty \
      (
        name = "Hershey Font",
        description = "name of Hershey font to use",
        items = list_hershey_fonts(),
      )
    delete_text = bpy.props.BoolProperty \
      (
        name = "Delete Original Text",
        description = "delete the original text object",
        default = False
      )

    @classmethod
    def poll(celf, context) :
        active_object = context.scene.objects.active
        return \
            (
                context.mode == "OBJECT"
            and
                active_object != None
            #and
            #    active_object.select
            and
                active_object.type in ("FONT", "CURVE")
            )
    #end poll

    def draw(self, context) :
        the_col = self.layout.column(align = True)
        the_col.label("Hershey Font:")
        the_col.prop(self, "font_name")
        the_col.prop(self, "delete_text")
    #end draw

    def action_common(self, context, redoing) :
        try :
            if not redoing :
                text_object = context.scene.objects.active
                if text_object == None or not text_object.select :
                    raise Failure("no selected object")
                #end if
                if text_object.type != "FONT" or type(text_object.data) != bpy.types.TextCurve :
                    raise Failure("need to operate on a font object")
                #end if
                # save the name of the object so I can find it again
                # when I'm reexecuted. Can't save a direct reference,
                # as that is likely to become invalid. Blender guarantees
                # the name is unique anyway.
                self.orig_object_name = text_object.name
            else :
                text_object = context.scene.objects[self.orig_object_name]
                assert text_object.type == "FONT" and type(text_object.data) == bpy.types.TextCurve
            #end if
            if self.font_name != " " :
                the_font = hershey_font.HersheyGlyphs.load(self.font_name)
            else :
                the_font = None
            #end if
            curve_name = text_object.name + " hersh"
            curve_data = bpy.data.curves.new(curve_name, "CURVE")
            if the_font != None :
                scaling = \
                    (
                        mathutils.Matrix.Scale
                          (
                            -1, # factor
                            4, # size
                            mathutils.Vector((0, 1, 0)), # axis
                          ) # flip Y-axis
                    *
                        mathutils.Matrix.Scale
                          (
                            the_font.scale, # factor
                            4 # size
                          )
                    )
                text_data = text_object.data
                # TODO: text boxes, character formats
                pos = mathutils.Vector((0, 0, 0))
                for ch in text_data.body :
                    if the_font.encoding != None :
                        glyph_nr = the_font.encoding.get(ord(ch))
                    else :
                        glyph_nr = ord(ch)
                    #end if
                    if glyph_nr != None :
                        the_glyph = the_font.glyphs.get(glyph_nr)
                    else :
                        the_glyph = None
                    #end if
                    # note each new curve Spline already seems to have one point to begin with
                    if the_glyph != None :
                        glyph_width = the_glyph.max_x - the_glyph.min_x
                        for pathseg in the_glyph.path :
                            curve_spline = curve_data.splines.new("POLY")
                            for i, point in enumerate(pathseg) :
                                if i != 0 :
                                    curve_spline.points.add()
                                #end if
                                curve_spline.points[i].co = \
                                    (
                                        mathutils.Matrix.Translation(pos)
                                    *
                                        scaling
                                    *
                                        mathutils.Vector((point.x, point.y - the_font.baseline_y, 0))
                                    ).resized(4)
                            #end for
                        #end for
                    else :
                        glyph_width = the_font.max.x - the_font.min.x
                        curve_spline = curve_data.splines.new("POLY")
                        curve_spline.points.add(3)
                        for i, corner_x, corner_y in \
                            (
                                (0, the_font.min.x, the_font.min.y),
                                (1, the_font.max.x, the_font.min.y),
                                (2, the_font.max.x, the_font.max.y),
                                (3, the_font.min.x, the_font.max.y),
                            ) \
                        :
                            curve_spline.points[i].co = \
                                (
                                    mathutils.Matrix.Translation(pos)
                                *
                                    scaling
                                *
                                    mathutils.Vector((corner_x, corner_y - the_font.baseline_y, 0))
                                ).resized(4)
                        #end for
                        curve_spline.use_cyclic_u = True
                    #end if
                    pos += mathutils.Vector((glyph_width * the_font.scale, 0, 0))
                #end for
            #end if
            curve_obj = bpy.data.objects.new(curve_name, curve_data)
            context.scene.objects.link(curve_obj)
            curve_obj.matrix_local = curve_obj.matrix_local
            bpy.ops.object.select_all(action = "DESELECT")
            bpy.data.objects[curve_name].select = True
            context.scene.objects.active = curve_obj
            if self.delete_text :
                context.scene.objects.unlink(text_object)
                bpy.data.objects.remove(text_object)
            #end if
            # all done
            status = {"FINISHED"}
        except Failure as why :
            sys.stderr.write("Failure: {}\n".format(why.msg)) # debug
            self.report({"ERROR"}, why.msg)
            status = {"CANCELLED"}
        #end try
        return \
            status
    #end action_common

    def execute(self, context) :
        return \
            self.action_common(context, True)
    #end execute

    def invoke(self, context, event) :
        return \
            self.action_common(context, False)
    #end invoke

#end HersheyText

def add_invoke_button(self, context) :
    if HersheyText.poll(context) :
        the_col = self.layout.column(align = True) # gives a nicer grouping of my items
        the_col.label("Hersheyfy:")
        the_col.operator(HersheyText.bl_idname, text = "Do It")
    #end if
#end add_invoke_button

def register() :
    bpy.utils.register_module(__name__)
    bpy.types.VIEW3D_PT_tools_object.append(add_invoke_button)
#end register

def unregister() :
    bpy.utils.unregister_module(__name__)
    bpy.types.VIEW3D_PT_tools_object.remove(add_invoke_button)
#end unregister

if __name__ == "__main__" :
    register()
#end if
