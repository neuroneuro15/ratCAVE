__author__ = 'nickdg'

import os
import time
import numpy as np
from scipy import stats
import pdb

from matplotlib import pyplot as plt
from sklearn.neighbors import NearestNeighbors
from sklearn.decomposition import PCA
from psychopy import event, core
import pandas as pd

import ratcave
from ratcave.devices.trackers.optitrack import Optitrack
from ratcave.graphics import *
from ratcave.graphics.core import utils

np.set_printoptions(precision=3, suppress=True)

def scan(optitrack_ip="127.0.0.1"):
    """Project a series of points onto the arena, collect their 3d position, and save them and the associated
    rigid body data into a pickled file."""


    # Check that cameras are in correct configuration (only visible light, no LEDs on, in Segment tracking mode, everything calibrated)
    tracker = Optitrack(client_ip=optitrack_ip)
    assert "Arena" in tracker.rigid_bodies, "Must Add Arena Rigid Body in Motive!"
    wavefront_reader = WavefrontReader(ratcave.graphics.resources.obj_primitives)
    mesh = wavefront_reader.get_mesh('Grid', centered=True, lighting=False, scale=1.5, drawstyle='point', point_size=10)
    mesh.material.diffuse.rgb = 1, 1, 1
    mesh.world.position=[0, 0, -1]

    scene = Scene([mesh])
    scene.camera.ortho_mode = True

    window = Window(scene, screen=1, fullscr=True)

    #start drawing.
    data = {'markerPos': [], 'bodyPos': [], 'bodyRot': [], 'screenPos': []}
    clock = core.CountdownTimer(30)
    while ('escape' not in event.getKeys()) and clock.getTime() > 0:

        # Draw Circle
        amp, speed = .03, 5.

        scene.camera.position[:2] = (amp * np.sin(clock.getTime() * speed)), (amp * np.cos(clock.getTime() * speed))
        # scene.camera.position[:2] = np.random.uniform(-1.2, 1.2), np.random.uniform(-.85, .85)  # Change circle position to a random one.
        window.draw()
        window.flip()

        time.sleep(.016)

        new_position = tracker.get_unidentified_positions(1)

        if new_position:

            # Try to get Arena rigid body and a single unidentified marker
            try:
                body = tracker.rigid_bodies['Arena']
            except KeyError:
                raise KeyError("Cannot find Arena in Motive.  Please Add a Rigid Body called 'Arena' in Movie and try again!")

            # If successful, add the new position to the list.
            feedback = bool(new_position and body)
            if feedback:
                data['markerPos'].append(new_position[0])
                data['bodyPos'].append(body.position)
                data['bodyRot'].append(body.rotation)
        else:
            print("No point detected.")

    window.close()
    return data


def normal_nearest_neighbors(data, n_neighbors=40, min_dist_filter=.04):
    """Find the normal direction of a hopefully-planar cluster of n_neighbors"""

    # K-Nearest neighbors on whole dataset
    nbrs = NearestNeighbors(n_neighbors).fit(data)
    distances, indices = nbrs.kneighbors(data)

    # PCA on each cluster of k-nearest neighbors
    latent_all, normal_all = [], []
    for dist_array, idx_array in zip(distances, indices):

        if np.min(dist_array) < min_dist_filter: # Filter out huge distances for outliers:
            pp = PCA(n_components=3).fit(data[idx_array, :]) # Perform PCA

             # Get the percent variance of each component
            latent_all.append(pp.explained_variance_ratio_)

            # Get the normal of the plane along the third component (flip if pointing in -y direction)
            normal = pp.components_[2] if pp.components_[2][1] > 0 else -pp.components_[2]
            normal_all.append(normal)

    # Convert to NumPy Array and return
    return np.array(normal_all), np.array(latent_all)


def meshify(data, filename):

    ## IMPORT DATA ##
    # Put values of data dictionary into numpy arrays.
    body_positions, body_rotations = np.array(data['bodyPos']), np.array(data['bodyRot'])
    points = pd.DataFrame(data['markerPos'], columns=['x', 'y', 'z'])
    points['mask'] = True  # Identifies which rows are used in the analysis (will be updated as filters are run)

    # Plot raw marker data as 3D Scatterplot
    """
    fig = plt.figure()
    ax = fig.add_subplot(221, projection='3d')
    lims = utils.plot3_square(ax, np.array(data[['x', 'y', 'z']]))
    plt.show()
    """

    ## REMOVE OUTLIERS ##
    # Remove Obviously Bad Points according to Height
    points['mask'] &= (-.02 < points['y']) & (points['y'] < .52)   # TODO: Automatize Height-based point filtering.

    # Filter out data that's not within a clear plane (mainly corners and outliers)
    normals, explained_variances = normal_nearest_neighbors(np.array(points[['x', 'y', 'z']]))
    points['mask'] &= explained_variances[:,2] < .005  #

    # Add normal data to each point
    points = pd.concat([points, pd.DataFrame(normals, columns=['nx', 'ny', 'nz'])], axis=1)


    ## CLUSTER INTO SEPARATE WALL PLANES ##
    # Label Markers by Clustering of their normals
    points['wall'] = None
    walls = pd.DataFrame(columns=['nx', 'ny', 'nz', 'x', 'y', 'z'])
    for wall in range(5):
        # Cluster from a random point, taking only points within a given distance (normal direction) from it
        print("Making Wall {0}.  Points left to assign: {1}".format(wall, sum(points['wall'].notnull()==False)))
        pdb.set_trace()

        normal_data = points.loc[points['mask'] & points['wall'].notnull()==False, ['nx', 'ny', 'nz']]
        center_idx = np.random.choice(normal_data.index.values)

        wall_mask = np.sqrt(((normal_data - normal_data.ix[center_idx])**2).sum(axis=1)) < .5
        points.loc[wall_mask, 'wall'] = wall

        # Get Mean position and normal from the cluster of points, filtering again to get rid of any outliers (so much filtering!)
        wall_data = points[['x', 'y', 'z']].ix[wall_mask]
        rotated_data = PCA(n_components=3).fit(wall_data).transform(wall_data)[:,2]
        mean, std, threshold = np.mean(rotated_data), np.std(rotated_data), 1.5
        mask = (mean - (threshold * std) < rotated_data) * (rotated_data < (mean + (threshold *std)))
        points.loc[wall_data.index, 'mask'] &= mask

        # Get normal and offset position for each wall
        normal = PCA(n_components=3).fit(wall_data.ix[mask]).components_[2]
        normal = -normal if normal[1] < 0 else normal
        offset = wall_data.ix[mask].mean()
        walls.loc[wall, ['nx', 'ny', 'nz', 'x', 'y', 'z']] = np.append(normal, offset)

    pdb.set_trace()

    """
    # Plot Box with labeled Sides
    ax = fig.add_subplot(222, projection='3d')
    for data, color in zip(data_clustered, 'rgybm'):
        utils.plot3_square(ax, data, color, lims=lims)
    """
    ## CALCULATE WALL NORMAL AND CENTER ##
    normals, offsets = [], []
    ax = fig.add_subplot(223, projection='3d')

    ## CALCULATE PLANE INTERSECTIONS TO GET VERTICES ##
    # Want equation in form ax + by + cz = d.  So, get d from norm and offsets
    d = np.sum(normals * offsets, axis=1)

    # Find floor plane
    floor_mask = normals[:,1] == normals[:,1].max()
    floor_normal, floor_dd = normals[floor_mask, :], d[floor_mask]
    wall_mask = floor_mask == False
    wall_normals, wall_dd = normals[wall_mask, :], d[wall_mask]

    ceiling_norm, ceiling_dd = np.array([0., 1., 0.]), .6  # TODO: Have it auto-find highest point.

    #
    num_walls = 4
    floor_verts, ceiling_verts = np.zeros((num_walls, 3)), np.zeros((num_walls, 3))
    floor_vertnorms = np.zeros((num_walls, 3))
    ceil_vertnorms = np.zeros((num_walls, 3))
    idx = 0
    wn, wd = wall_normals[0], wall_dd[0]
    while idx < 4:
        # Find nearest wall to the left by finding two nearest wall normals (distance), and the positive y cross product
        distance = lambda x, xx: np.sqrt(np.sum((x-xx)**2, axis=1))
        yy = distance(wn, wall_normals)
        mask = (stats.rankdata(yy) > 1) * (stats.rankdata(yy) < 4)
        cross_prod = np.cross(wn, wall_normals[mask])
        adj_wall_idx = np.where(mask)[0][np.where(cross_prod[:,1]>0)[0]]  # Complicated, but works.  Fix later.
        adj_wall_norm, adj_wall_dd = wall_normals[adj_wall_idx], wall_dd[adj_wall_idx]

        # Calculate intersection of this wall with adjacent wall and floor.
        def find_intersection((wn1, wn2, wn3), (d1, d2, d3)):
            """Solve system of 3 Equations to get intersection point between three planes."""
            abc_mat, d_mat = np.vstack((wn1, wn2, wn3)), np.vstack((d1, d2, d3))
            return np.linalg.solve(abc_mat, d_mat).transpose()

        print (wn, adj_wall_norm, floor_normal)
        floor_intersection = find_intersection((wn, adj_wall_norm, floor_normal), (wd, adj_wall_dd, floor_dd))

        ceil_intersection = find_intersection((wn, adj_wall_norm, ceiling_norm), (wd, adj_wall_dd, ceiling_dd))

        floor_verts[idx, :] = floor_intersection
        ceiling_verts[idx, :] = ceil_intersection

        # Find average direction of the intersecting planes for the vertex (essential for a short normal list)
        normalize = lambda x: x/ np.sqrt(np.sum(x**2))
        fvn = normalize(wn + adj_wall_norm + floor_normal)
        cvn = normalize(wn + adj_wall_norm)
        floor_vertnorms[idx, :] = fvn
        ceil_vertnorms[idx, :] = cvn

        wn, wd = adj_wall_norm, adj_wall_dd
        idx +=1

    ## BUILD VERTEX, NORMAL, AND FACE INDICES FROM VERTEX DATA ##

    # Build quad face index list
    quad_faces = []
    quad_faces.append([0, 1, 2, 3])  # Add the floor first, to match normals order!
    for idx in range(len(floor_verts)):  # Add all the walls
        idx2 = idx+1 if idx<len(floor_verts)-1 else 0
        quad_faces.append([idx, idx2, len(floor_verts)+idx2, len(floor_verts)+idx])


    # Make new vertex and normals lists, so they match the face_indices order (will be unncecessaryily long
    vertices = np.vstack((floor_verts, ceiling_verts)) - np.mean(body_positions, axis=0)
    normals = np.vstack((floor_normal, wall_normals))

    ## WRITE WAVEFRONT .OBJ FILE FOR IMPORTING INTO BLENDER ##
    with open(filename, 'wb') as wavfile:

        header = "# Blender v2.69 (sub 5) OBJ File: ''\n" + "# www.blender.org\n" + "o Arena\n"
        wavfile.write(header)

        for vert in vertices:
            vertline = "v {0} {1} {2} \n".format(*vert)
            wavfile.write(vertline)

        for norm in normals:
            normline = "vn {0} {1} {2}\n".format(norm[0], norm[1], norm[2])
            wavfile.write(normline)

        for idx, face in enumerate(quad_faces):
            faceline = 'f'
            for f in face:
                faceline += r" {f}//{n}".format(f=f+1, n=idx+1)
            faceline += '\n'
            wavfile.write(faceline)


    # Make final plot with drawing of reconstructed object.
    ax = fig.add_subplot(224, projection='3d')
    for face_inds, color in zip(quad_faces, 'rgybm'):
        data = np.vstack((vertices[face_inds, :], vertices[face_inds[0], :]))
        utils.plot3_square(ax, data, color+':', limits=lims)

    plt.show()


if __name__ == '__main__':
    # Run the specified function from the command line. Format: arena_scanner function_name file_name
    print("Starting the Scan Process...")
    data = scan()
    print("Analyzing and Saving to {0}".format(ratcave.data_dir))
    meshify(data, filename=os.path.join(ratcave.data_dir, 'arena_unprocessed.obj'))
    print("Save done.  Please import file into blender and export as arena.obj before using in experiments!")

