import numpy as np
import random, time
from utils import distEuclidean
from data_types import Point

# # #{ class Tree
class Tree:
    def __init__(self, root_coordinates):
        self.nodes = {}
        self.add_node(root_coordinates, None, 0)
        self.valid = False

    def add_node(self, coordinates, parent, cost):
        self.nodes[coordinates] = {'parent': parent, 'cost': cost}

    def get_parent(self, node_coordinates):
        return self.nodes[node_coordinates]['parent']

    def rewire(self, node_coordinates, parent, cost):
        self.add_node(node_coordinates, parent, cost)

    def get_cost(self, node_coordinates):
        return self.nodes[node_coordinates]['cost']

    def find_path(self, end_node, start_node_hdg):

        path = []
        current_parent = end_node

        stop = False
        while not stop:
            coords = (current_parent[0], current_parent[1], current_parent[2], None)
            current_parent = self.get_parent(current_parent)

            if current_parent is None:
                coords = (coords[0], coords[1], coords[2], start_node_hdg) 
                stop   = True

            path.append(coords)

        # Return path from start point to end point.
        path.reverse()

        return path
# # #}

# # #{ class RRT
class RRT:

    def __init__(self):
        pass

    # # #{ generatePath()
    def generatePath(self, g_start, g_end, path_planner, rrtstar=False, straighten=False):

        print("[INFO] {:s}: Searching for path from [{:.2f}, {:.2f}, {:.2f}] to [{:.2f}, {:.2f}, {:.2f}].".format('RRT*' if rrtstar else 'RRT', g_start[0], g_start[1], g_start[2], g_end[0], g_end[1], g_end[2]))
        self.start = tuple(g_start[0:3])
        self.end   = tuple(g_end[0:3])

        self.tree              = Tree(self.start)
        self.bounds            = path_planner['bounds']
        self.kdtree            = path_planner['obstacles_kdtree']
        self.safety_distance   = path_planner['safety_distance']
        self.timeout           = path_planner['timeout']
        
        self.gaussian_sampling = path_planner['rrt/sampling/method'] == 'gaussian'
        if self.gaussian_sampling:
            self.gaussian_sampling_sigma_inflation = path_planner['rrt/sampling/gaussian/stddev_inflation']
        
        rrtstar_neighborhood = path_planner['rrtstar/neighborhood'] if rrtstar else None

        # build tree
        self.buildTree(branch_size=path_planner['rrt/branch_size'], rrtstar_neighborhood=rrtstar_neighborhood)

        if not self.tree.valid:
            return None, None

        # find path
        path = self.tree.find_path(self.end, g_start[3])

        # smooth the path
        if straighten:
            for i in range(2):
                path = self.halveAndTest(path)

        distance = 0.0
        for i in range(1, len(path)):
            distance += distEuclidean(path[i - 1], path[i])

        # print('rrt path:', path)

        return path, distance
    # # #}

    # # #{ pointValid()
    def pointValid(self, point, check_bounds=True):

        if check_bounds and not self.bounds.valid(point):
            return False

        # check if point is at least safety_distance away from the nearest obstacle
        nn_dist, _  = self.kdtree.query(point.asList(), k=1)
        return nn_dist > self.safety_distance
    # # #}

    # # #{ getRandomPoint()
    def getRandomPoint(self):
        # Select a random point which is
        #  1) within world bounds and 
        #  2) is collision-free

        point       = None
        point_valid = False
        while not point_valid:
            x = random.uniform(self.bounds.point_min.x, self.bounds.point_max.x)
            y = random.uniform(self.bounds.point_min.y, self.bounds.point_max.y)
            z = random.uniform(self.bounds.point_min.z, self.bounds.point_max.z)
            print(x)
            point = Point(x, y, z)

            point_valid = self.pointValid(point)

        return point.asTuple()
    # # #}

    # # #{ getRandomPointGaussian()
    def getRandomPointGaussian(self, sigma_offset=0.0):
        
        # Compute mean and standard deviation
        st, en = [self.start[i] for i in range(3)], [self.end[i] for i in range(3)]
        mean   = np.mean([st, en], axis=0)
        sigma  = np.std([st, en], axis=0)

        # Inflate zero stddev
        for i in range(3):
            if sigma[i] < 1e-3:
                sigma[i] = 0.1

        point       = None
        point_valid = False
        while not point_valid:

            #raise NotImplementedError('[STUDENTS TODO] Implement Gaussian sampling in RRT to speed up the process and narrow the paths.')
            # Tips:
            #  - sample from Normal distribution: use numpy.random.normal (https://numpy.org/doc/stable/reference/random/generated/numpy.random.normal.html)
            #  - to prevent deadlocks when sampling continuously, increase the sampling space by inflating the standard deviation of the gaussian sampling

            # STUDENTS TODO: Sample XYZ in the state space
            x = np.random.normal(mean[0], sigma[0], 1)
            y = np.random.normal(mean[1], sigma[1], 1)
            z = np.random.normal(mean[2], sigma[2], 1)
            #sigma = sigma + self.gaussian_sampling_sigma_inflation * sigma
            #x = 0
            #y = 0
            #z = 0
            point = Point(x[0], y[0], z[0])
            point_valid = self.pointValid(point)

        return point.asTuple()
    # # #}

    # # #{ getClosestPoint()
    def getClosestPoint(self, point):

        # Go through all points in tree and return the closest one to point. Uses euclidian metric.
        min_distance = np.finfo(np.float32).max
        cl_point     = self.start

        for p in self.tree.nodes:
            distance = distEuclidean(point, p)
            if distance < min_distance:
                min_distance = distance
                cl_point = p

        return cl_point
    # # #}

    # # #{ setDistance()
    def setDistance(self, p_from, p_to, length):
        vec      = np.array([p_to[0] - p_from[0], p_to[1] - p_from[1], p_to[2] - p_from[2]])
        vec_norm = np.linalg.norm(vec)
        if vec_norm < length:
            return p_to

        vec = length * vec / vec_norm
        return (p_from[0] + vec[0], p_from[1] + vec[1], p_from[2] + vec[2])
    # # #}

    # # #{ validateLinePath()
    def validateLinePath(self, p_from, p_to, discretization_factor=0.1, check_bounds=True):

        v_from      = np.array([p_from[0], p_from[1], p_from[2]])
        v_to        = np.array([p_to[0], p_to[1], p_to[2]])
        v_from_to   = v_to - v_from
        len_from_to = np.linalg.norm(v_from_to)

        len_ptr = 0.0
        while len_ptr < len_from_to:
            p_ptr = v_from + len_ptr * v_from_to
            if not self.pointValid(Point(p_ptr[0], p_ptr[1], p_ptr[2]), check_bounds):
                return False
            len_ptr += discretization_factor
       
        return self.pointValid(Point(p_to[0], p_to[1], p_to[2]))

    # # #}

    # # #{ getPointsInNeighborhood()
    def getPointsInNeighborhood(self, point, neighborhood):
        points = []
        for p in self.tree.nodes:
            if distEuclidean(point, p) < neighborhood:
                if self.validateLinePath(point, p):
                    points.append(p)
        return points
    # # #}

    # # #{ rewire()
    def rewire(self, point, neighborhood):
        # Rewiring - if cost through given point is lower than its own, rewire it to go through that point.
        point_cost = self.tree.get_cost(point)
        for neighbor in self.getPointsInNeighborhood(point, neighborhood):
            rewired_cost = point_cost + distEuclidean(neighbor, point)
            if rewired_cost < self.tree.get_cost(neighbor):
                self.tree.rewire(neighbor, point, rewired_cost)
    # # #}

    # # #{ getParentWithOptimalCost()
    def getParentWithOptimalCost(self, point, closest_point, neighborhood):

        parent = closest_point
        cost   = self.tree.get_cost(closest_point) + distEuclidean(closest_point, point)

        neighborhood_points = self.getPointsInNeighborhood(point, neighborhood)
        for neighbor in neighborhood_points:

            #raise NotImplementedError('[STUDENTS TODO] Getting node parents in RRT* not implemented. You have to finish it.')
            # Tips:
            #  - look for neighbor which when connected yields minimal path cost all the way back to the start
            #  - you might need functions 'self.tree.get_cost()' or 'distEuclidean()'

            # TODO: fill these two variables
            #cost = float('inf')
            cost_now   = self.tree.get_cost(neighbor) + distEuclidean(neighbor, point)
            if cost_now < cost:
                parent = neighbor
                cost = cost_now
        return parent, cost
    # # #}

    # # #{ buildTree()
    def buildTree(self, branch_size, rrtstar_neighborhood=None):

        rrtstar                      = rrtstar_neighborhood is not None
        start_time                   = time.time()
        rrt_gaussian_sigma_inflation = 0.0

        while not self.tree.valid:

            point         = self.getRandomPoint() if not self.gaussian_sampling else self.getRandomPointGaussian(rrt_gaussian_sigma_inflation)
            closest_point = self.getClosestPoint(point)
           
            # normalize vector closest_point->point to length of branch_size
            point = self.setDistance(closest_point, point, branch_size)

            if self.validateLinePath(point, closest_point):

                if not rrtstar:
                    parent, cost = closest_point, distEuclidean(point, closest_point)
                else:
                    # RRT*: Choose neighbor which will provide the best cost.
                    parent, cost = self.getParentWithOptimalCost(point, closest_point, rrtstar_neighborhood)

                self.tree.add_node(point, parent, cost)

                if rrtstar:
                    # RRT*: Rewire all neighbors
                    self.rewire(point, rrtstar_neighborhood)

                # Check, whether end is reachable. If yes, stop the tree generation.
                if distEuclidean(point, self.end) < branch_size and self.validateLinePath(point, self.end):
                    self.tree.add_node(self.end, point, self.tree.get_cost(point) + distEuclidean(self.end, point))
                    self.tree.valid = True
            
            # Gaussian sampling: increase standard deviation of the sampling Normal distribution
            elif self.gaussian_sampling:
                rrt_gaussian_sigma_inflation += self.gaussian_sampling_sigma_inflation

            if time.time() - start_time > self.timeout:
                print("[ERROR] {:s}: Timeout limit in buildTree() exceeded ({:.1f} s > {:.1f} s). Ending.".format('RRT*' if rrtstar else 'RRT', time.time() - start_time, self.timeout))
                return
    # # #}

    # # #{ halveAndTest()
    def halveAndTest(self, path):
        pt1 = path[0][0:3]
        pt2 = path[-1][0:3]
        
        if len(path) <= 2:
            return path

        #raise NotImplementedError('[STUDENTS TODO] RRT: path straightening is not finished. Finish it on your own.')
        # Tips:
        #  - divide the given path by a certain ratio and use this method recursively
        path_0 = path
        if not self.validateLinePath(pt1, pt2, check_bounds=False):
            # [STUDENTS TODO] Replace seg1 and seg2 variables effectively
            NumFail = 0
            while NumFail < 4 and len(path_0) > 3:
                num = random.randint(0,len(path_0)-1)
                ptn = path_0[num][0:3]
                if self.validateLinePath(pt1, ptn, check_bounds=False) and self.validateLinePath(ptn, pt2, check_bounds=False):
                   #print("coming inside 1")
                   seg1 = [path_0[0]]
                   seg2 = [path_0[num]]
                   seg3 = [path_0[-1]]
                   seg1.extend(seg2)
                   seg1.extend(seg3)
                   NumFail = 4

                if self.validateLinePath(pt1, ptn, check_bounds=False) and not self.validateLinePath(ptn, pt2, check_bounds=False):
                   #print("coming inside 2")
                   #print(ptn)
                   num_now = num
                   seg1 = [path_0[0]]
                   seg2 = path_0[num_now:]
                   #print(seg2)
                   #print(ptn)
                   seg1.extend(seg2)
                   NumFail = NumFail + 1
                
                if not self.validateLinePath(pt1, ptn, check_bounds=False) and self.validateLinePath(ptn, pt2, check_bounds=False):
                   #print("coming inside 3")
                   #print(num)
                   num_now = num + 1
                   seg1 = path_0[:num_now]
                   #print(seg1)
                   #print(ptn)
                   seg2 = [path_0[-1]]
                   seg1.extend(seg2)
                   NumFail = NumFail + 1

                if not self.validateLinePath(pt1, ptn, check_bounds=False) and not self.validateLinePath(ptn, pt2, check_bounds=False):
                   #print("coming inside 4")
                   seg1 = path_0
                   NumFail = NumFail + 1
                path_0 = seg1
            return path_0
        
        return [path[0], path[-1]]
    # # #}

# # #}
