import os

from gym import error, spaces
from gym.utils import seeding
import numpy as np
from os import path
import gym
import copy
import six

from gym.envs.dart.static_window import *
from gym.envs.dart.KR5_arm import MyWorld

try:
    import pydart2 as pydart
    from pydart2.gui.trackball import Trackball
except ImportError as e:
    raise error.DependencyNotInstalled("{}. (HINT: you need to install pydart2.)".format(e))


class KR5Env(gym.Env):
    """Superclass for all Dart environments.
    """

    def __init__(self):
        self.num_bodies = 2
        self.num_actions = 2
        self.variable_size = False
        action_bounds = np.array([[-1 for i in range(self.num_actions)], [1 for i in range(self.num_actions)]])
        self.mass_range = np.array([1, 7])
        self.size_range = np.array([0.1, 0.1])
        # self.size_range = np.array([0.05,0.2])
        self.mass = np.random.uniform(self.mass_range[0], self.mass_range[1], self.num_bodies)
        self.size = np.random.uniform(self.size_range[0], self.size_range[1], [self.num_bodies, 2])
        # self.size = np.sort(self.size)
        # pydart.init()
        print('pydart initialization OK')

        self.dart_world = MyWorld(self.num_bodies, self.num_actions, is_flip=False)
        self.box_skeleton = self.dart_world.skeletons[0]  # select block skeleton
        self.action_space = spaces.Box(action_bounds[0, :], action_bounds[1, :])
        self.obs_dim = 2 + self.num_bodies + 2
        high = np.inf * np.ones(self.obs_dim)
        low = -high
        mass_bounds = np.pad(np.array([[self.mass_range[0], self.mass_range[1]]]), ((0, self.num_bodies - 1), (0, 0)),
                             'edge')
        self.observation_space = spaces.Dict(
            {"observation": spaces.Box(low, high), "mass": spaces.Box(mass_bounds[:, 0], mass_bounds[:, 1])})
        # self.observation_space = spaces.Box(low, high)
        for jt in range(0, len(self.box_skeleton.joints)):
            if self.box_skeleton.joints[jt].has_position_limit(0):
                self.box_skeleton.joints[jt].set_position_limit_enforced(True)

        # self.observation_space = spaces.Box(low, high)
        self._seed()
        for i in range(self.num_bodies):
            self.box_skeleton.bodynodes[i].set_mass(self.mass[i])
            self.box_skeleton.bodynodes[i].shapenodes[0].shape.set_size([0.07, 0.04, self.size[i, 0]])
            self.box_skeleton.bodynodes[i].shapenodes[1].shape.set_size([0.07, 0.04, self.size[i, 0]])
        CTJ = self.box_skeleton.joints[1].transform_from_child_body_node()
        CTJ[2, 3] = -(self.size[0, 0] + self.size[1, 0] - 0.1) * 0.5
        self.box_skeleton.joints[1].set_transform_from_child_body_node(CTJ)
        # CTJ = self.box_skeleton.joints[0].transform_from_child_body_node()
        # CTJ[0,3] += (self.size[0, 1]*0.25-0.035)
        # self.box_skeleton.joints[0].set_transform_from_child_body_node(CTJ)
        self.count_act = 0
        self.viewer = None

        self.metadata = {
            'render.modes': ['human', 'rgb_array'],
            'video.frames_per_second': int(np.round(1.0 / self.dt))
        }

    def _seed(self, seed=None):
        print('set_seed', seed)
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    # methods to override:
    # ----------------------------
    def reset_model(self):
        self.dart_world.reset()
        # self.dart_world.reset_box()
        self.mass = self.np_random.uniform(self.mass_range[0], self.mass_range[1], self.num_bodies)
        self.size = np.random.uniform(self.size_range[0], self.size_range[1], [self.num_bodies, 2])
        # self.size = np.sort(self.size)
        for i in range(self.num_bodies):
            self.box_skeleton.bodynodes[i].set_mass(self.mass[i])
            self.box_skeleton.bodynodes[i].shapenodes[0].shape.set_size([0.07, 0.04, self.size[i, 0]])
            self.box_skeleton.bodynodes[i].shapenodes[1].shape.set_size([0.07, 0.04, self.size[i, 0]])

        CTJ = self.box_skeleton.joints[1].transform_from_child_body_node()
        CTJ[2, 3] = -(self.size[0, 0] + self.size[1, 0] - 0.1) * 0.5
        self.box_skeleton.joints[1].set_transform_from_child_body_node(CTJ)

        # CTJ = self.box_skeleton.joints[0].transform_from_child_body_node()
        # CTJ[0,3] += (self.size[0, 1]*0.25-0.035)
        # self.box_skeleton.joints[0].set_transform_from_child_body_node(CTJ)
        # self.dart_world.reset()

    def viewer_setup(self):
        """
        This method is called when the viewer is initialized and after every reset
        Optionally implement this method, if you need to tinker with camera position
        and so forth.
        """
        pass

    # -----------------------------

    def _reset(self):
        self.reset_model()

        ob = self.get_obs()
        self.count_act = 0
        return ob

    @property
    def dt(self):
        return self.dart_world.dt

    def do_simulation(self, tau):
        self.dart_world.controller.tau = tau
        # self.dart_world.controller.offset = offset
        self.dart_world.step()

    def _step(self, action):
        action[0] = action[0] * 100 + 200
        action[1] = action[1] * self.size[0, 0] * 0.40 * 0.0001
        self.count_act += 1
        # print(self.count_act)
        while True:
            if self.dart_world.complete:
                break
            self.do_simulation(action)
            self.render(mode='human')
            # if self.dart_world.t > 0.4:
            #     print("Gone mad")
            # break

        self.dart_world.complete = False
        # self.render(mode='human')
        obs = self.get_obs()
        if self.count_act >= self.num_bodies:
            done = True
            self.count_act = 0
        else:
            done = False
        reward = 0

        return obs, 0, done, {}

    def get_obs(self):
        joints = [6 + i for i in range(self.num_bodies - 1)]
        idx = [1, 3, 5]
        idx.extend(joints)
        obs = np.append(np.hstack((self.box_skeleton.q[idx], self.dart_world.init_vel[idx])),
                        [self.size[0, 0], self.size[1, 0]])
        return {'observation': obs, 'mass': self.mass}

    def _render(self, mode='human', close=False):
        # self._get_viewer().scene.tb.trans[0] = -self.dart_world.skeletons[self.track_skeleton_id].com()[0]*1
        if close:
            if self.viewer is not None:
                self._get_viewer().close()
                self.viewer = None
            return

        if mode == 'rgb_array':
            data = self._get_viewer(str(self.mass[0])).getFrame()
            return data
        elif mode == 'human':
            self._get_viewer().runSingleStep()

    def getViewer(self, sim, title=None):
        # glutInit(sys.argv)
        win = StaticGLUTWindow(sim, title)
        win.scene.add_camera(Trackball(theta=-45.0, phi=0.0, zoom=0.1), 'gym_camera')
        win.scene.set_camera(win.scene.num_cameras() - 1)
        win.run()
        return win

    def _get_viewer(self, title='win'):
        if self.viewer is None:
            self.viewer = self.getViewer(self.dart_world, title)
            self.viewer_setup()
        return self.viewer

    def state_vector(self):
        return np.concatenate([
            self.box_skeleton.q,
            self.box_skeleton.dq
        ])