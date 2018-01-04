
from os import path
from .shader import Shader
from collections import namedtuple


"""
Here are some sample obj files for prototyping your app!
"""

# This is an easy way to get the filepaths of some oft-used resources for displaying simple scenes.

resource_path = path.join(path.split(__file__)[0], '..', 'assets')

# Images
img_uvgrid = path.join(resource_path,'uvgrid.png')
img_colorgrid = path.join(resource_path, 'colorgrid.png')
img_white = path.join(resource_path, 'white.png')

# Meshes
obj_primitives = path.join(resource_path, 'primitives.obj')
obj_grid3D = path.join(resource_path, 'grid3D.obj')


# Shaders
shader_path = path.join(path.split(__file__)[0], '..', 'shaders')

# General, Normal Shaders
default_shader = Shader.from_file(vert=path.join(shader_path, 'combShader.vert'),
                                  frag=path.join(shader_path, 'combShader.frag'),
                                  lazy=True)

shadow_shader = Shader.from_file(vert=path.join(shader_path, 'shadowShader.vert'),
                                frag=path.join(shader_path, 'shadowShader.frag'),
                                 lazy=True)

deferred_shader = Shader.from_file(vert=path.join(shader_path, 'basicDeferred.vert'),
                                  frag=path.join(shader_path, 'basicDeferred.frag'),
                                   lazy=True)

