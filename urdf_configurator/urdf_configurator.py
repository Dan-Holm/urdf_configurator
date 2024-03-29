
import os
import sys
import argparse
import urdf_parser_py.urdf as urdf
import rclpy
import rclpy.node
from std_msgs.msg import String
from rclpy.qos import QoSProfile, QoSDurabilityPolicy
from geometry_msgs.msg import TransformStamped
import tf2_ros
# import euler to quaternion conversion





class assemblySetup():
    def __init__(self):
        pass

    def configure_assembly(self, link_name, joint_name, parent_name, child_name, joint_type, joint_origin_xyz, joint_origin_rpy):

            # create new joint
            self.joint = urdf.Joint(name=joint_name, joint_type=joint_type, parent=parent_name, child=child_name)
            self.joint.origin = urdf.Pose(xyz=joint_origin_xyz, rpy=joint_origin_rpy)
            self.link = urdf.Link(name=link_name,)
            # print(self.urdf.links[-1])
            self.link.inertial = urdf.Inertial(mass=1, inertia=urdf.Inertia(ixx=1, ixy=0, ixz=0, iyy=1, iyz=0, izz=1), origin=urdf.Pose(xyz=[0, 0, 0], rpy=[0, 0, 0]))
            visual = urdf.Visual(geometry=urdf.Cylinder(length=1, radius=1), material=urdf.Material(color=urdf.Color(0.3, 0.3, 0.3, 1.0), name='dark'), origin=urdf.Pose(xyz=[0, 0, 0], rpy=[0, 0, 0]))
            collision = urdf.Collision(geometry=urdf.Cylinder(length=1, radius=1), origin=urdf.Pose(xyz=[0, 0, 0], rpy=[0, 0, 0]))
            self.link.visual = visual
            self.link.collision = collision

    def get_link(self):
        return self.link
    def get_joint(self):
        return self.joint

    def add_visual(self, link, geometry, material, name):
        visual = urdf.Visual(geometry=geometry, material=material, name=name)
        link.visual = visual

    def add_collision(self, link, geometry, pose):
        collision = urdf.Collision(geometry=geometry, origin=pose)
        link.collision = collision

    def add_inertial(self, link, mass, inertia, pose):
        inertial = urdf.Inertial(mass=mass, inertia=inertia, origin=pose)
        link.inertial = inertial

    def add_joint_pose(self, joint, pose):
        joint.origin = pose
class UrdfConfigurator(rclpy.node.Node):

    def __init__(self, description_file=None, description_topic=None):
        super().__init__('urdf_configurator_node') #,  automatically_declare_parameters_from_overrides=True)
        if description_file is not None:
            # If we were given a URDF file on the command-line, use that.
            self.load_urdf(description_file)

        elif description_topic is not None:
            # If we were given a topic to listen to, use that.
            self.description_topic = description_topic
            # self.description_subscriber = self.create_subscription(String, self.description_topic, self.description_callback, 10)
        else:
            # Creating new empty URDF from scratch
            self.new_urdf()
            

        self.static_tf_broadcaster = tf2_ros.StaticTransformBroadcaster(self)
        # self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
   

    def new_urdf(self):
        self.urdf = urdf.URDF()
        return self.urdf

    def load_urdf(self, description_file):
        self.urdf = urdf.URDF.from_xml_file(description_file)
        self.configure_robot(self.urdf)
        self.publishURDF()
        # self.publish_static_transforms(self.urdf.child_map)

    def configure_robot(self, description):
        self.links = description.links
        self.joints = description.joints
        self.robot_name = description.name

    def publishURDF(self):
        # create transient local publisher, for latched topic
        latching_qos = QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.urdf_publisher = self.create_publisher(String, 'robot_description_debug',  qos_profile=latching_qos) 
        new_urdf_string = self.urdf.to_xml_string()
        String_msg = String()
        String_msg.data = new_urdf_string
        # self.get_logger().info('Publishing new URDF:\n%s' % new_urdf_string)
        self.urdf_publisher.publish(String_msg)

    def add_link(self, link):
        self.urdf.add_link(link)

    def get_link_from_name(self, name):
        return [link for link in self.links if link.name == name][0]
    

    def get_link_names(self):
        return [link.name for link in self.links]

    def get_robot(self):
        return self.urdf
    
    def update_robot(self):
        self.publishURDF()
        self.publish_static_transforms(self.urdf.child_map)

    def origin_to_transofrm(self, origin):

        if origin is None:
            return TransformStamped()
        
        translation = origin.xyz
        rotation = origin.rpy
        
        transform = TransformStamped()
        transform.transform.translation.x = translation[0]
        transform.transform.translation.y = translation[1]
        transform.transform.translation.z = translation[2]
        transform.transform.rotation.x = 0.0
        transform.transform.rotation.y = 0.0
        transform.transform.rotation.z = 0.0
        transform.transform.rotation.w = 1.0

        return transform

    def publish_transforms(self, joints):
        frame_prefix = ''
        time = self.get_clock().now().to_msg()
        tf_transforms = []

        for joint in joints:
            tf_transform = self.origin_to_transofrm(joint.origin)
            tf_transform.header.stamp = time
            tf_transform.header.frame_id = frame_prefix + joint.name
            tf_transform.child_frame_id = frame_prefix + joint.child
            tf_transforms.append(tf_transform)

        self.tf_broadcaster.sendTransform(tf_transforms)

    def publish_static_transforms(self, child_map):
        frame_prefix = ''

        tf_transforms = []

        for parent in child_map.keys():
            for child in child_map[parent]:

                child_index = [index for (index, item) in enumerate(self.urdf.joints) if item.name == child[0]]
                tf_transform = TransformStamped()
                if child_index:
                    tf_transform = self.origin_to_transofrm(self.joints[child_index[0]].origin)
                tf_transform.header.frame_id = frame_prefix + parent
                tf_transform.child_frame_id = frame_prefix + child[1]
                tf_transform.transform.rotation.w = 1.0
                tf_transforms.append(tf_transform)

        self.static_tf_broadcaster.sendTransform(tf_transforms)

        


def main():
    print('Hi from urdf_configurator.')

    rclpy.init()
    stripped_args = rclpy.utilities.remove_ros_args(args=sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'description_file', help='Robot description file to use', nargs='?', default=None)

    # Parse the remaining arguments, noting that the passed-in args must *not*
    # contain the name of the program.
    parsed_args = parser.parse_args(args=stripped_args[1:])
    # uc = UrdfConfigurator('/home/daniel/master_ws/src/Danitech-master/wagon_description/urdf/wagon.urdf')
    uc = UrdfConfigurator('/home/daniel/playground/turlebot4/src/turtlebot4/turtlebot4_description/urdf/standard/turtlebot4.urdf')

    try:
        rclpy.spin(uc)
    except KeyboardInterrupt:
        pass

    uc.destroy_node()
    rclpy.try_shutdown()
    # args = rclpy.cli.arguments.parse(['--ros-args', '--remap', 'chatter:=hello'])

    # parser = argparse.ArgumentParser(description='Process some integers.')


if __name__ == '__main__':
    main()
