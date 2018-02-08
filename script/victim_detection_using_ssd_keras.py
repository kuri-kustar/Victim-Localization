#! /usr/bin/python

import rospy
import std_msgs.msg
import cv2
import keras
import tensorflow as tf
from keras.applications.imagenet_utils import preprocess_input
from keras.backend.tensorflow_backend import set_session
from keras.models import Model
from keras.preprocessing import image
import pickle
import numpy as np
from random import shuffle
from scipy.misc import imread, imresize
from timeit import default_timer as timer

from std_msgs.msg import String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

import sys
sys.path.append('/home/abdulrahman/catkin_ws/src/victim_localization/resources/ssd_keras')
from ssd_utils import BBoxUtility
from ssd import SSD300 as SSD

import time

# import custom msg
from victim_localization.msg import DL_msgs_box
from victim_localization.msg import DL_msgs_boxes
from victim_localization.srv import DL_box

class ssdKeras():
    def __init__(self):
        self.node_name = "ssd_keras"
        rospy.init_node(self.node_name)
        self.class_names = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"]
        self.num_classes = len(self.class_names)
        self.input_shape = (300,300,3)
        self.model = SSD(self.input_shape,num_classes=self.num_classes)
        self.model.load_weights('/home/abdulrahman/catkin_ws/src/victim_localization/resources/ssd_keras/weights_SSD300.hdf5')

        self.bbox_util = BBoxUtility(self.num_classes)
        self.conf_thresh = 0.4

        self.model._make_predict_function()
        self.graph = tf.get_default_graph()

        self.detection_index=DL_msgs_boxes()

        # Create unique and somewhat visually distinguishable bright
        # colors for the different classes.
        self.class_colors = []
        for i in range(0, self.num_classes):
            # This can probably be written in a more elegant manner
            hue = 255*i/self.num_classes
            col = np.zeros((1,1,3)).astype("uint8")
            col[0][0][0] = hue
            col[0][0][1] = 128 # Saturation
            col[0][0][2] = 255 # Value
            cvcol = cv2.cvtColor(col, cv2.COLOR_HSV2BGR)
            col = (int(cvcol[0][0][0]), int(cvcol[0][0][1]), int(cvcol[0][0][2]))
            self.class_colors.append(col)

        self.bridge = CvBridge() # Create the cv_bridge object

        self.Image_Status = "Not_Ready"
        self.StartImage= cv2.imread('/home/abdulrahman/catkin_ws/src/victim_localization/resources/start.jpg')
        self.to_draw=cv2.resize(self.StartImage, (640, 480))

        self.image_sub = rospy.Subscriber("/floating_sensor/camera/rgb/image_raw", Image, self.detect_image,queue_size=1)  # the appropriate callbacks

        self.box_coordinate_pub = rospy.Publisher("/ssd_detction/box", DL_msgs_boxes ,queue_size=5)  # the appropriate callbacks
        self.SSD_Serv = rospy.Service('SSD_Detection', DL_box, self.SSD_Detection_Server)


    def detect_image(self, ros_image):

    #### Use cv_bridge() to convert the ROS image to OpenCV format  ####
        try:
            self.image_orig = self.bridge.imgmsg_to_cv2(ros_image, "bgr8")
        except CvBridgeError as e:
            print(e)
    ##########

        self.Image_Status="Ready"
        cv2.imshow("SSD result", self.to_draw)
        cv2.waitKey(1)



    def SSD_Detection_Server(self, req):
        """
        # Arguments
        conf_thresh: Threshold of confidence. Any boxes with lower confidence
                     are not visualized.
        """
        if self.Image_Status!="Ready":
            return
        vidw = 640.0 # change from cv2.cv.CV_CAP_PROP_FRAME_WIDTH
        vidh = 480.0 # change from cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
        vidar = vidw/vidh

        #print(type(image_orig))
        im_size = (self.input_shape[0], self.input_shape[1])
        resized = cv2.resize(self.image_orig, im_size)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Reshape to original aspect ratio for later visualization
        # The resized version is used, to visualize what kind of resolution
        # the network has to work with.
        self.to_draw = cv2.resize(resized, (640, 480))

        # Use model to predict
        inputs = [image.img_to_array(rgb)]
        tmp_inp = np.array(inputs)
        x = preprocess_input(tmp_inp)

        start_time = time.time() #debuggin

        with self.graph.as_default():
            y = self.model.predict(x)
        #print("--- %s seconds_for_one_image ---" % (time.time() - start_time))

        # This line creates a new TensorFlow device every time. Is there a
        # way to avoid that?

        results = self.bbox_util.detection_out(y)



        #initiaze the detection msgs

        box_msg = DL_box()
        box_msg.xmin=0
        box_msg.ymin=0
        box_msg.xmax=0
        box_msg.ymax=0
        box_msg.Class="Non" # 100 reflect a non-class value

        if len(results) > 0 and len(results[0]) > 0:

        # Interpret output, only one frame is used
            det_label = results[0][:, 0]
            det_conf = results[0][:, 1]
            det_xmin = results[0][:, 2]
            det_ymin = results[0][:, 3]
            det_xmax = results[0][:, 4]
            det_ymax = results[0][:, 5]


            top_indices = [i for i, conf in enumerate(det_conf) if conf >= self.conf_thresh]

            top_conf = det_conf[top_indices]


            top_label_indices = det_label[top_indices].tolist()
            top_xmin = det_xmin[top_indices]
            top_ymin = det_ymin[top_indices]
            top_xmax = det_xmax[top_indices]
            top_ymax = det_ymax[top_indices]


            print(conf)
            for i in range(top_conf.shape[0]):
                    self.detection_index.boxes[:]=[]
                    xmin = int(round(top_xmin[i] * self.to_draw.shape[1]))
                    ymin = int(round(top_ymin[i] * self.to_draw.shape[0]))
                    xmax = int(round(top_xmax[i] * self.to_draw.shape[1]))
                    ymax = int(round(top_ymax[i] * self.to_draw.shape[0]))

                    #include the corner to be published
                    box_msg.xmin=xmin
                    box_msg.ymin=ymin
                    box_msg.xmax=xmax
                    box_msg.ymax=ymax
                    box_msg.Class=self.class_names[int(top_label_indices[i])]
                    #self.detection_index.boxes.append(box_msg)

                    # Draw the box on top of the to_draw image

                    class_num = int(top_label_indices[i])
                    if (self.class_names[class_num]=="person"):
                        cv2.rectangle(self.to_draw, (xmin, ymin), (xmax, ymax),
                                      self.class_colors[class_num], 2)
                        text = self.class_names[class_num] + " " + ('%.2f' % top_conf[i])

                        text_top = (xmin, ymin-10)
                        text_bot = (xmin + 80, ymin + 5)
                        text_pos = (xmin + 5, ymin)
                        cv2.rectangle(self.to_draw, text_top, text_bot, self.class_colors[class_num], -1)
                        cv2.putText(self.to_draw, text, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0,0,0), 1)

        return  (box_msg.xmin,box_msg.ymin,box_msg.xmax,box_msg.ymax,box_msg.Class)



def main(args):
        try:
                ssdKeras()
                rospy.spin()
        except KeyboardInterrupt:
                print "Shutting down vision node."
                cv.DestroyAllWindows()


if __name__ == '__main__':
        main(sys.argv)

