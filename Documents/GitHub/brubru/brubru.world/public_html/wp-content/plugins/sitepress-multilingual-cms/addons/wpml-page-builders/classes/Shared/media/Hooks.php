<?php

namespace WPML\PB\Media;

class Hooks implements \IWPML_Frontend_Action, \IWPML_Backend_Action, \IWPML_DIC_Action {

	/** @var \WPML_PB_Integration $pbIntegration */
	private $pbIntegration;

	/** @var array $media_finders */
	private $media_finders = [];

	public function __construct( \WPML_PB_Integration $pbIntegration ) {
		$this->pbIntegration = $pbIntegration;
	}

	public function add_hooks() {
		add_action( 'wpml_pb_find_used_media_in_post', [ $this, 'findUsedMediaInPost' ] );
		add_filter( 'wpml_pb_get_used_media_in_post', [ $this, 'getUsedMediaInPost' ] );
	}

	/**
	 * @param \WP_Post $post
	 */
	public function findUsedMediaInPost( $post ) {
		if ( $this->pbIntegration->is_post_status_ok( $post ) ) {
			foreach ( $this->get_media_finders( $post ) as $updater ) {
				$updater->find_media( $post );
			}
		}
	}

	/**
	 * @param \WP_Post $post
	 *
	 * @return array
	 */
	public function getUsedMediaInPost( $post ) {
		$mediaData = [];

		foreach ( $this->get_media_finders( $post ) as $updater ) {
			$mediaData = array_merge(
				$mediaData,
				$updater->get_media()
			);
		}

		return $mediaData;
	}

	/**
	 * @param \WP_Post $post
	 *
	 * @return \IWPML_PB_Media_Update[]
	 */
	private function get_media_finders( $post ) {
		if ( ! isset( $this->media_finders[ $post->ID ] ) ) {
			/**
			 * Gets all media updaters.
			 *
			 * @param \IWPML_PB_Media_Update[] $media_updaters
			 * @param \WP_Post                 $post
			 */
			$this->media_finders[ $post->ID ] = apply_filters( 'wpml_pb_get_media_finders', [], $post );
		}

		return $this->media_finders[ $post->ID ];
	}
}
