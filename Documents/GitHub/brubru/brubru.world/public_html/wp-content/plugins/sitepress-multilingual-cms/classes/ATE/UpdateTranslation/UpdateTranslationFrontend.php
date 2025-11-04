<?php

namespace WPML\TM\ATE\UpdateTranslation;

use WPML\Core\WP\App\Resources;
use WPML\FP\Fns;
use WPML\FP\Obj;
use WPML\FP\Logic;
use WPML\FP\Relation;
use WPML\LIB\WP\Hooks;
use WPML\TM\API\Jobs;
use WPML\TM\ATE\Review\PreviewLink;
use WPML\TM\ATE\UpdateTranslation\UpdateTranslation;
use function WPML\FP\pipe;


class UpdateTranslationFrontend implements \IWPML_Frontend_Action, \IWPML_Backend_Action {

    public function add_hooks() {
		if ( ! self::hasValidNonce() ) {
			Hooks::onAction( 'template_redirect' )
				->then( [ $this, 'handleUpdateTranslationFrontend' ] );
		}
    }

	public function handleUpdateTranslationFrontend() {
		if ( ! $this->shouldHandleRequest() ) {
			return;
		}

		$post = $this->getPostCurrentPostObject();
		if ( ! $post ) {
			return;
		}

		$jobId = $this->getJobIdFromCurrentPost( $post );

		if ( $jobId ) {
			Hooks::onAction( 'wp_footer' )
				->then( [ $this, 'printUpdateTranslationAnchor' ] );

			$enqueue = Resources::enqueueApp( 'updateTranslationFrontend' );
			$enqueue( $this->getTranslationFrontendData( $jobId, $post ) );
		}
	}

	private static function hasValidNonce() {
		$get = Obj::prop( Fns::__, $_GET );

		return (bool) \wp_verify_nonce(
			$get( 'preview_nonce' ),
			PreviewLink::getNonceName( (int) $get( 'preview_id' ) )
		);
	}

	/**
	 * Checks if the current request should be handled by this class.
	 *
	 * @return bool
	 */
	private function shouldHandleRequest() {
		global $wpml_translation_job_factory;
		$isAteEnabled = ! is_null( $wpml_translation_job_factory );
		return is_main_query()
			&& have_posts()
			&& $isAteEnabled
			&& Obj::prop( 'ate_job_id', $_GET )
			&& ! Obj::prop( 'back', $_GET );
	}

	/**
	 * Get the job id from the current post.
	 *
	 * @param \WP_Post $post
	 * @return int|null
	 */
	private function getJobIdFromCurrentPost( $post ) {
		global $sitepress, $wpml_translation_job_factory;

		$trid  = $sitepress->get_element_trid( $post->ID, 'post_' . $post->post_type );
		$lang  = $sitepress->get_language_for_element( $post->ID, 'post_' . $post->post_type );
		$jobId = $wpml_translation_job_factory->job_id_by_trid_and_lang( $trid, $lang );

		return $jobId;
	}

	/**
	 * Get the current post object.
	 *
	 * @return \WP_Post|null
	 */
	private function getPostCurrentPostObject() {
		$post_id = get_queried_object_id();
		if ( ! $post_id ) {
			return null;
		}

		$post = get_post( $post_id );
		if ( ! $post ) {
			return null;
		}

		return $post;
	}

	public function printUpdateTranslationAnchor() {
		echo '
            <script type="text/javascript" >
               var ajaxurl = "' . \admin_url( 'admin-ajax.php', 'relative' ) . '"
            </script>
            <div id="wpml_update_translation_frontend"></div>
        ';
	}

	/**
	 * Get the data for the translation post on the frontend.
	 *
	 * @param $jobId
	 * @param $post
	 * @return array
	 */
	public function getTranslationFrontendData( $jobId, $post ) {
		$job = Jobs::get( $jobId );
		if ( ! $job ) {
			return [];
		}

		return [
			'name' => 'updateTranslation',
			'data' => [
				'jobId'              => (int) $jobId,
				'postId'             => $post->ID,
				'completedInATE'     => $this->isCompletedInATE( $_GET ),
				'isReturningFromATE' => (bool) Obj::prop( 'ate_job_id', $_GET ),
				'clickedBackInATE'   => (bool) Obj::prop( 'back', $_GET ),
				'needsUpdate'        => Jobs::shouldBeATESynced( $job ),
				'endpoints'          => [
					'update' => UpdateTranslation::class
				],
			]
		];
	}

	/**
	 * Returns completed status based on key 'complete_no_changes' in $params.
	 * Returns NOT_COMPLETED if 'complete_no_changes' is not set.
	 *
	 * @param array $params
	 *
	 * @return string
	 */
	public function isCompletedInATE( $params ) {
		$completedInATE = pipe(
			Obj::prop( 'complete_no_changes' ),
			'strval',
			Logic::cond( [
				[ Relation::equals( '1' ), Fns::always( 'COMPLETED_WITHOUT_CHANGED' ) ],
				[ Relation::equals( '0' ), Fns::always( 'COMPLETED' ) ],
				[ Fns::always( true ), Fns::always( 'NOT_COMPLETED' ) ],
			] )
		);

		return $completedInATE( $params );
	}

}
