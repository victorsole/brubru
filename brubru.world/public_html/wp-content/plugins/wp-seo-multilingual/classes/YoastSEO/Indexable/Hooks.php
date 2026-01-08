<?php

namespace WPML\WPSEO\YoastSEO\Indexable;

use WPML\LIB\WP\WPDB;
use Yoast\WP\SEO\Main;
use Yoast\WP\SEO\Models\Indexable;
use Yoast\WP\SEO\Repositories\Indexable_Repository;
use Yoast\WP\SEO\Surfaces\Classes_Surface;

class Hooks implements \IWPML_Backend_Action, \IWPML_Frontend_Action, \IWPML_DIC_Action {

	/** @var \wpdb */
	private $wpdb;

	/**
	 * @param \wpdb $wpdb
	 */
	public function __construct( \wpdb $wpdb ) {
		$this->wpdb = $wpdb;
	}

	public function add_hooks() {
		add_action( 'icl_pro_translation_completed', [ $this, 'invalidateIndexables' ], 10, 3 );
	}

	/**
	 * @param int       $postId
	 * @param array     $fields
	 * @param \stdClass $job
	 */
	public function invalidateIndexables( $postId, $fields, $job ) {
		if ( $postId ) {
			$this->invalidatePostIndexable( $postId );
		} elseif ( 'package_yoast-seo' === $job->original_post_type ) {
			$this->invalidateTermIndexables();
		}
	}

	/**
	 * @param int $postId
	 */
	private function invalidatePostIndexable( $postId ) {
		/** @var Main $yoastSEO */
		$yoastSEO = YoastSEO();

		/** @var Classes_Surface $classes */
		$classes = $yoastSEO->classes;

		/** @var Indexable_Repository $indexable_repository */
		$indexable_repository = $classes->get( Indexable_Repository::class );

		/** @var Indexable|null $indexable */
		$indexable = $indexable_repository->find_by_id_and_type( $postId, 'post', false );
		if ( $indexable ) {
			$indexable->version = 0;
			$indexable->save();
		}
	}

	private function invalidateTermIndexables() {
		WPDB::withoutError(
			function () {
				$this->wpdb->query(
					/* phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared */
					"UPDATE {$this->wpdb->prefix}yoast_indexable SET version = 0 WHERE object_type = 'term'"
				);
			}
		);
	}
}
