<?php

namespace WPML\TM\Settings;

use WPML\Collect\Support\Collection;
use WPML\Core\BackgroundTask\Command\UpdateBackgroundTask;
use WPML\Core\BackgroundTask\Model\BackgroundTask;
use WPML\BackgroundTask\AbstractTaskEndpoint;
use WPML\Core\BackgroundTask\Service\BackgroundTaskService;
use WPML\FP\Obj;
use WPML\LIB\WP\Attachment;
use WPML\MediaTranslation\PostWithMediaFiles;
use WPML\MediaTranslation\PostWithMediaFilesFactory;
use WPML\MediaTranslation\UsageOfMediaFilesInPosts;

class ProcessExistingMediaInPosts extends AbstractTaskEndpoint {
	const LOCK_TIME         = 5;
	const MAX_RETRIES       = 10;
	const DESCRIPTION       = 'Processing media in posts.';
	const POSTS_PER_REQUEST = 40;

	/** @var \wpdb */
	private $wpdb;

	/** @var PostWithMediaFilesFactory $postWithMediaFilesFactory */
	private $postWithMediaFilesFactory;

	/** $var UsageOfMediaFilesInPosts $usageOfMediaFilesInPosts */
	private $usageOfMediaFilesInPosts;

	private $postsPerRequest = self::POSTS_PER_REQUEST;

	/**
	 * @param \wpdb                     $wpdb
	 * @param UpdateBackgroundTask      $updateBackgroundTask
	 * @param BackgroundTaskService     $backgroundTaskService
	 * @param PostWithMediaFilesFactory $postWithMediaFilesFactory
	 * @param UsageOfMediaFilesInPosts  $usageOfMediaFilesInPosts
	 */
	public function __construct(
		\wpdb $wpdb,
		UpdateBackgroundTask $updateBackgroundTask,
		BackgroundTaskService $backgroundTaskService,
		PostWithMediaFilesFactory $postWithMediaFilesFactory,
		UsageOfMediaFilesInPosts $usageOfMediaFilesInPosts
	) {
		$this->wpdb                      = $wpdb;
		$this->postWithMediaFilesFactory = $postWithMediaFilesFactory;
		$this->usageOfMediaFilesInPosts  = $usageOfMediaFilesInPosts;

		parent::__construct( $updateBackgroundTask, $backgroundTaskService );
	}

	public function setPostsPerRequest( $postsPerRequest ) {
		$this->postsPerRequest = $postsPerRequest;
	}

	public function runBackgroundTask( BackgroundTask $task ) {
		$payload = $task->getPayload();
		$page    = Obj::propOr( 1, 'page', $payload );
		$postIds = $this->getPosts( $page );

		if ( count( $postIds ) > 0 ) {
			$this->processExistingMediaInPosts( $postIds );
			$payload['page'] = $page + 1;
			$task->setPayload( $payload );
			$task->addCompletedCount( count( $postIds ) );
			$task->setRetryCount(0 );
			if ( $task->getCompletedCount() >= $task->getTotalCount() ) {
				$task->finish();
			}
		} else {
			$task->finish();
		}
		return $task;
	}

	public function getDescription( Collection $data ) {
		return __( self::DESCRIPTION, 'sitepress' );
	}

	public function getTotalRecords( Collection $data ) {
		return $this->getPostsCount();
	}

	private function getAllowedPostTypes() {
		$allowedTypes = [
			'post',
			'page',
			'product',
			'portfolio',
			'project',
			'elementor_library',
			'vc_templates',
			'so_panels',
			'gallery',
			'slides',
			'slider'
		];

		return $allowedTypes;
	}

	/**
	 * @param int $page
	 *
	 * @return array
	 */
	private function getPosts( $page ) {
		$postTypes = $this->getAllowedPostTypes();
		if ( count( $postTypes ) === 0 ) {
			return [];
		}

		return $this->wpdb->get_col(
			$this->wpdb->prepare(
				"SELECT DISTINCT p.ID
						FROM {$this->wpdb->posts} AS p
						INNER JOIN {$this->wpdb->prefix}icl_translations t ON t.element_id = p.ID
						WHERE t.source_language_code IS NULL
						AND p.post_status NOT IN ('auto-draft', 'trash', 'inherit')
						AND p.post_type IN (" . wpml_prepare_in( $postTypes, '%s' ) . ")
						ORDER BY p.ID ASC
						LIMIT %d OFFSET %d",
				$this->postsPerRequest,
				($page-1)*$this->postsPerRequest
			)
		);
	}

	/**
	 * @return int
	 */
	private function getPostsCount() {
		$postTypes = $this->getAllowedPostTypes();
		if ( count( $postTypes ) === 0 ) {
			return 0;
		}

		// phpcs:disable WordPress.DB.PreparedSQL.InterpolatedNotPrepared
		return (int) $this->wpdb->get_var(
			"SELECT COUNT(DISTINCT(p.ID))
					FROM {$this->wpdb->posts} AS p
					INNER JOIN {$this->wpdb->prefix}icl_translations t ON t.element_id = p.ID
					WHERE t.source_language_code IS NULL
					AND p.post_status NOT IN ('auto-draft', 'trash', 'inherit')
					AND p.post_type IN (" . wpml_prepare_in( $postTypes, '%s' ) . ")"
		);
	}

	/**
	 * @param array $postIds
	 */
	private function processExistingMediaInPosts( array $postIds ) {
		$batch = [];
		foreach ( $postIds as $postId ) {
			$postMedia        = $this->postWithMediaFilesFactory->create( $postId );
			$data             = $postMedia->get_media_data_from_post_content_and_meta( false );
			$batch[ $postId ] = $data;
		}

		if ( count( $batch ) === 0 ) {
			return;
		}

		$urls = [];
		foreach ( $batch as $post_media_data ) {
			if ( is_array( $post_media_data ) && isset( $post_media_data[0] ) && isset( $post_media_data[1] ) ) {
				$copied_media_file_ids     = is_array( $post_media_data[0] ) ? $post_media_data[0] : [];
				$referenced_media_file_ids = is_array( $post_media_data[1] ) ? $post_media_data[1] : [];

				$this->extractUrlsFromMediaFileAttributes( $urls, $copied_media_file_ids );
				$this->extractUrlsFromMediaFileAttributes( $urls, $referenced_media_file_ids );
			}
		}

		// get all posts ids by attachment urls in one query
		$urlsToPostIds = Attachment::attachmentUrlsToPostIds( $urls );
		Attachment::addToCache( $urlsToPostIds );

		$all_media_ids = [];
		foreach ( $batch as &$post_media_data ) {
			if ( ! is_array( $post_media_data ) ) {
				continue;
			}

			if ( isset( $post_media_data[0] ) ) {
				$this->findAttachmentIds( $post_media_data[0] );
				$this->filterOnlyWithAttachmentIds( $post_media_data[0] );
			}

			if ( isset( $post_media_data[1] ) ) {
				$this->findAttachmentIds( $post_media_data[1] );
				$this->filterOnlyWithAttachmentIds( $post_media_data[1] );
			}

			$post_media_data = PostWithMediaFiles::extract_media_ids( $post_media_data );
			$all_media_ids = array_merge( $all_media_ids, $post_media_data[0], $post_media_data[1] );
		}

		$all_media_ids = array_values( array_unique( $all_media_ids ) );
		$all_usages    = [];
		foreach ( $all_media_ids as $media_id ) {
			$all_usages[ $media_id ] = $this->usageOfMediaFilesInPosts->getUsagesFromPostMeta( $media_id, UsageOfMediaFilesInPosts::USAGES_FIELD_NAME );
		}

		foreach ( $batch as $post_id => &$post_media_data ) {
			if ( ! is_array( $post_media_data ) || ! isset( $post_media_data[0] ) || ! isset( $post_media_data[1] ) ) {
				continue;
			}

			$usages = $this->usageOfMediaFilesInPosts->getUsages(
				$post_id,
				[],
				[],
				$post_media_data[0],
				$post_media_data[1],
				$all_usages
			);
			foreach ( $usages as $media_id => $media_usages ) {
				$all_usages[ $media_id ] = $media_usages;
			}
		}

		$this->resavePostmetaForEachBatch( $batch, $all_usages );
	}

	private function extractUrlsFromMediaFileAttributes( &$urls, $media_file_ids ) {
		foreach ( $media_file_ids as $media_file_id ) {
			if (
				array_key_exists( 'attachment_id', $media_file_id ) &&
				is_numeric( $media_file_id['attachment_id'] ) &&
				(int) $media_file_id['attachment_id'] > 0
			) {
				continue;
			}
			$urls[] = Attachment::extractSrcFromAttributes( $media_file_id );
		}
	}

	private function findAttachmentIds( &$post_media_data ) {
		foreach ( $post_media_data as &$media_file_id ) {
			if (
				array_key_exists( 'attachment_id', $media_file_id ) &&
				is_null( $media_file_id['attachment_id'] )
			) {
				$media_file_id['attachment_id'] = Attachment::idFromUrlCache( Attachment::extractSrcFromAttributes( $media_file_id ) );
			}
		}
	}

	private function filterOnlyWithAttachmentIds( &$post_media_data ) {
		$post_media_data = array_values(
			array_filter(
				$post_media_data,
				function ( $media_file_id ) {
					return array_key_exists( 'attachment_id', $media_file_id ) && is_numeric( $media_file_id['attachment_id'] );
				}
			)
		);
	}

	private function resavePostmetaForEachBatch( $batch, $all_usages ) {
		$meta_keys = [
			PostWithMediaFiles::COPIED_MEDIA_IDS_SETTING,
			PostWithMediaFiles::REFERENCED_MEDIA_IDS_SETTING,
			UsageOfMediaFilesInPosts::USAGES_FIELD_NAME,
		];

		$values       = [];
		$placeholders = [];
		$all_post_ids = [];

		foreach ( $batch as $post_id => $data ) {
			list( $copied, $referenced ) = $data;

			$copied     = array_map( 'intval', $copied );
			$referenced = array_map( 'intval', $referenced );

			$copied     = maybe_serialize( $copied );
			$referenced = maybe_serialize( $referenced );

			$placeholders[] = "(%d,'" . $meta_keys[0] . "',%s)";
			$values[]       = $post_id;
			$values[]       = $copied;

			$placeholders[] = "(%d,'" . $meta_keys[1] . "',%s)";
			$values[]       = $post_id;
			$values[]       = $referenced;

			$all_post_ids[] = $post_id;
		}

		foreach ( $all_usages as $media_file_id => $usages_in_posts ) {
			$usages_in_posts = array_map( function( $arr ) {
				return is_array( $arr ) ? array_map( 'intval', $arr ) : $arr;
			}, $usages_in_posts );

			$placeholders[] = "(%d,'" . $meta_keys[2] . "',%s)";
			$values[]       = $media_file_id;
			$values[]       = maybe_serialize( $usages_in_posts );
			$all_post_ids[] = $media_file_id;
		}

		$sql = "
            DELETE FROM {$this->wpdb->postmeta}
            WHERE post_id IN (" . wpml_prepare_in( $all_post_ids, '%d' ) . ")
            AND meta_key IN (" . wpml_prepare_in( $meta_keys, '%s' ) . ")
        ";
		$this->wpdb->query( $sql );

		if ( ! empty( $values ) ) {
			$sql = "INSERT INTO {$this->wpdb->postmeta} (post_id, meta_key, meta_value) VALUES " . implode( ',', $placeholders );
			$this->wpdb->query( $this->wpdb->prepare( $sql, $values ) );
		}

		$all_post_ids = array_values( array_unique( $all_post_ids ) );

		foreach ( $all_post_ids as $post_id ) {
			wp_cache_delete( $post_id, 'post_meta' );
		}
	}
}
