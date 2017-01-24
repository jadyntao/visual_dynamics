from __future__ import division, print_function

import os

import argparse
import yaml

from visual_dynamics import envs
from visual_dynamics import policies
from visual_dynamics.envs import ServoingEnv
from visual_dynamics.utils.config import from_config
from visual_dynamics.utils.rl_util import do_rollouts, FeaturePredictorServoingImageVisualizer
from visual_dynamics.utils.transformer import transfer_image_transformer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('predictor_fname', type=str)
    parser.add_argument('algorithm_fname', type=str)
    parser.add_argument('--output_dir', '-o', type=str, default=None)
    parser.add_argument('--visualize', '-v', type=int, default=None)
    parser.add_argument('--record_file', '-r', type=str, default=None)
    parser.add_argument('--feature_inds', '-i', type=int, nargs='+', help='inds of subset of features to use')
    parser.add_argument('--w_init', type=float, default=10.0)
    parser.add_argument('--lambda_init', type=float, default=1.0)

    args = parser.parse_args()

    with open(args.predictor_fname) as predictor_file:
        predictor_config = yaml.load(predictor_file)

    if issubclass(predictor_config['environment_config']['class'], envs.Panda3dEnv):
        transfer_image_transformer(predictor_config)

    predictor = from_config(predictor_config)
    if args.feature_inds:
        args.feature_inds = [int(ind) for ind in args.feature_inds]
        predictor.feature_name = [predictor.feature_name[ind] for ind in args.feature_inds]
        predictor.next_feature_name = [predictor.next_feature_name[ind] for ind in args.feature_inds]

    if issubclass(predictor.environment_config['class'], envs.RosEnv):
        import rospy
        rospy.init_node("learn_visual_servoing")
    env = from_config(predictor.environment_config)
    if not isinstance(env, ServoingEnv):
        env = ServoingEnv(env)

    servoing_pol = policies.TheanoServoingPolicy(predictor, alpha=1.0, lambda_=args.lambda_init, w=args.w_init)

    with open(args.algorithm_fname) as algorithm_file:
        algorithm_config = yaml.load(algorithm_file)
    algorithm_config['env'] = env
    algorithm_config['servoing_pol'] = servoing_pol

    if 'snapshot_prefix' not in algorithm_config:
        snapshot_prefix = os.path.join(os.path.split(args.predictor_fname)[0],
                                       os.path.splitext(os.path.split(args.algorithm_fname)[1])[0],
                                       '')
        algorithm_config['snapshot_prefix'] = snapshot_prefix

    alg = from_config(algorithm_config)
    alg.run()

    if args.record_file and not args.visualize:
        args.visualize = 1
    if args.visualize:
        image_visualizer = FeaturePredictorServoingImageVisualizer(predictor, visualize=args.visualize)
        do_rollouts(env, servoing_pol, alg.num_trajs, alg.num_steps,
                          output_dir=args.output_dir,
                          image_visualizer=image_visualizer,
                          record_file=args.record_file,
                          verbose=True,
                          gamma=alg.gamma)


if __name__ == '__main__':
    main()
