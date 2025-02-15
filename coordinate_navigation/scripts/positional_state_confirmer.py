#!/usr/bin/env python
import rospy
import math

from tf.transformations import euler_from_quaternion

from std_msgs.msg import Bool

from apriltag_ros.msg import AprilTagDetectionArray
from geometry_msgs.msg import PoseWithCovarianceStamped

from std_srvs.srv import Trigger

from shapely.geometry import Point
from shapely.geometry import Polygon


class StateConfirmer(object):
    def __init__(self):

        # Initialize node
        rospy.init_node("state_confirmer")
        rospy.loginfo("state_confirmer node active")

        # Initialize service
        self.state_conf = rospy.Service("confirm_state", Trigger, self.confirm_state)
        rospy.loginfo("confirm_state service active")

        # Initialize Update State Publisher
        self.update_state_pub = rospy.Publisher("update_state", Bool, queue_size=1)
        self.rate = rospy.Rate(10)

        # Get state_conf tag param
        try:
            self.object_tags = rospy.get_param("object_tags")
            self.param_at_boundaries = rospy.get_param("at_boundaries")
            self.param_facing_boundaries = rospy.get_param("facing_boundaries")
        except (KeyError, rospy.ROSException):
            rospy.logerr("Error getting parameters.")
            raise ValueError

        self.at_boundaries = {}
        for boundary_name, boundary_edges in self.param_at_boundaries.items():
            edges = []
            for edge in boundary_edges:
                edges.append((edge[0], edge[1]))
            polygon = Polygon(edges)
            self.at_boundaries[boundary_name] = polygon

        self.facing_boundaries = {}
        for boundary_name, boundary_values in self.param_facing_boundaries.items():
            edges = []
            for edge in boundary_values["boundary"]:
                edges.append((edge[0], edge[1]))
            polygon = Polygon(edges)
            self.facing_boundaries[boundary_name] = polygon

        while not rospy.is_shutdown():
            rospy.spin()

    def confirm_state(self, req):
        # Wait for apriltag detections msg
        tag_detections = AprilTagDetectionArray()
        try:
            tag_detections = rospy.wait_for_message(
                "/tag_detections", AprilTagDetectionArray, rospy.Duration(1)
            )
        except rospy.ROSException:
            rospy.logwarn("Did not recieve 'tag_detections' message")

        detections = tag_detections.detections

        # Wait for odom msg
        odom_pose = rospy.wait_for_message(
            "/amcl_pose", PoseWithCovarianceStamped, rospy.Duration(1)
        )
        odom_pose = odom_pose.pose.pose

        # Set at
        at = "none"
        point = Point(odom_pose.position.x, odom_pose.position.y)
        for boundary_name, boundary_polygon in self.at_boundaries.items():
            if boundary_polygon.contains(point):
                at = boundary_name
                if boundary_name == "none":
                    break

        rospy.set_param("agents/turtlebot/at", [at])

        # Set facing
        facing = "nothing"
        set_flag = False
        # Set facing with april tag
        if len(detections) > 0:
            for detection in detections:
                tag_id = str(detection.id[0])

                try:
                    object_dict = self.object_tags[tag_id]
                    dist_threshold = object_dict["distance"]
                    rot_threshold = object_dict["orientation"]
                    predicates = object_dict["predicates"]
                    facing_ = predicates["facing"]
                except KeyError:
                    continue

                tag_pose = detection.pose.pose.pose

                r, p, y = euler_from_quaternion(
                    [
                        tag_pose.orientation.x,
                        tag_pose.orientation.y,
                        tag_pose.orientation.z,
                        tag_pose.orientation.w,
                    ]
                )
                if p > math.pi:
                    p -= 2 * math.pi

                if tag_pose.position.z <= dist_threshold and abs(p) <= rot_threshold:
                    set_flag = True
                    facing = facing_
        if not set_flag:
           
            for boundary_name, boundary_polygon in self.facing_boundaries.items():
                rospy.loginfo(boundary_name)
                if boundary_polygon.contains(point):
                    try:
                        rot_threshold = self.param_facing_boundaries[boundary_name]["orientation_thresh"]
                        orientation_boundary = self.param_facing_boundaries[boundary_name]["orientation"]
                    except KeyError as e:
                        rospy.loginfo("Key error: %s" % e)
                        continue

                    r, p, y = euler_from_quaternion(
                        [
                            odom_pose.orientation.x,
                            odom_pose.orientation.y,
                            odom_pose.orientation.z,
                            odom_pose.orientation.w,
                        ]
                    )

                    r_b, p_b, y_b = euler_from_quaternion(orientation_boundary)

                    if y > math.pi:
                        y -= 2 * math.pi
                    if y_b > math.pi:
                        y -= 2*math.pi

                    rospy.loginfo(max(y, y_b) - min(y, y_b))
                    if (max(y, y_b) - min(y, y_b)) <= rot_threshold:
                        cutoff_index = boundary_name.find("__")
                        if cutoff_index != -1:
                            boundary_name = boundary_name[:cutoff_index]

                        facing = boundary_name

        rospy.set_param("agents/turtlebot/facing", [facing])

        return True, "State confirmed"


if __name__ == "__main__":
    StateConfirmer()
