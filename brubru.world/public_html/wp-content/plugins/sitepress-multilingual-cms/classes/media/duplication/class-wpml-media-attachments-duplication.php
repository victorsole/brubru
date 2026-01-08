<?php

use WPML\FP\Obj;
use WPML\LIB\WP\Nonce;
use WPML\LIB\WP\User;
use WPML\Media\Option;
use WPML\MediaTranslation\PostWithMediaFiles;
use WPML\Core\BackgroundTask\Service\BackgroundTaskService;
use function WPML\Container\make;
use WPML\Records\Translations as TranslationRecords;
use WPML\TM\API\Jobs;

class WPML_Media_Attachments_Duplication {

	const WPML_MEDIA_PROCESSED_META_KEY = 'wpml_media_processed';

	/** @var  WPML_Model_Attachments */
	private $attachments_model;

	/** @var SitePress */
	private $sitepress;

	private $wpdb;

	private $language_resolution;

	/** @var PostWithMediaFilesFactory $post_media_factory */
	private $post_media_factory;

	/** @var BackgroundTaskService */
	private $background_task_service;

	private $original_thumbnail_ids = array();

	private $save_post_queue = [];

	private $translated_posts = [];

	/**
	 * WPML_Media_Attachments_Duplication constructor.
	 *
	 * @param SitePress              $sitepress
	 * @param WPML_Model_Attachments $attachments_model
	 *
	 * @internal param WPML_WP_API $wpml_wp_api
	 */
	public function __construct(
		SitePress $sitepress,
		WPML_Model_Attachments $attachments_model,
		wpdb $wpdb,
		WPML_Language_Resolution $language_resolution,
		\WPML\MediaTranslation\PostWithMediaFilesFactory $post_media_factory,
		BackgroundTaskService $background_task_service
	) {
		$this->sitepress               = $sitepress;
		$this->attachments_model       = $attachments_model;
		$this->post_media_factory      = $post_media_factory;
		$this->wpdb                    = $wpdb;
		$this->language_resolution     = $language_resolution;
		$this->post_media_factory      = $post_media_factory;
		$this->background_task_service = $background_task_service;
	}

	public function add_hooks() {
		// do not run this when user is importing posts in Tools > Import
		if ( ! isset( $_GET['import'] ) || $_GET['import'] !== 'wordpress' ) {
			add_action( 'add_attachment', array( $this, 'save_attachment_actions' ) );
			add_action( 'add_attachment', array( $this, 'save_translated_attachments' ) );
			add_filter( 'wp_generate_attachment_metadata', array( $this, 'wp_generate_attachment_metadata' ), 10, 2 );
		}

		$active_languages = $this->language_resolution->get_active_language_codes();

		if ( $this->is_admin_or_xmlrpc() && ! $this->is_uploading_plugin_or_theme() && 1 < count( $active_languages ) ) {
			add_action( 'edit_attachment', array( $this, 'save_attachment_actions' ) );
			add_action( 'icl_make_duplicate', array( $this, 'make_duplicate' ), 10, 4 );
		}

		$this->add_postmeta_hooks();

		add_action( 'save_post', array( $this, 'save_post_actions' ), 100, 2 );
		if ( Option::shouldHandleMediaAuto() ) {
			add_action( 'wp_after_insert_post', array( $this, 'extract_media_ids_from_post_content_and_meta' ), 100, 3 );
			add_action( 'woocommerce_after_product_object_save', array( $this, 'woocommerce_extract_media_ids_from_post_content_and_meta' ), 100, 2 );
			add_action( 'current_screen', array( $this, 'maybe_duplicate_original_post_media' ) );
		}
		add_action( 'before_delete_post', array( $this, 'delete_post_media_usages' ), 10, 1 );
		add_action( 'wpml_pro_translation_completed', array( $this, 'sync_on_translation_complete' ), 10, 3 );

		add_action( 'wp_ajax_wpml_media_translate_media', array( $this, 'ajax_batch_translate_media' ), 10, 0 );
		add_action( 'wp_ajax_wpml_media_duplicate_media', array( $this, 'ajax_batch_duplicate_media' ), 10, 0 );
		add_action( 'wp_ajax_wpml_media_duplicate_featured_images', array( $this, 'ajax_batch_duplicate_featured_images' ), 10, 0 );

		add_action( 'wp_ajax_wpml_media_mark_processed', array( $this, 'ajax_batch_mark_processed' ), 10, 0 );
		add_action( 'wp_ajax_wpml_media_scan_prepare', array( $this, 'ajax_batch_scan_prepare' ), 10, 0 );
		add_action( 'wp_ajax_wpml_media_save_should_handle_media_auto_setting', array( $this, 'ajax_save_should_handle_media_auto_setting' ), 10, 0 );

		add_action( 'wp_ajax_wpml_media_set_content_prepare', array( $this, 'set_content_defaults_prepare' ) );
		add_action( 'wpml_loaded', array( $this, 'add_settings_hooks' ) );
		add_action( 'admin_notices', array( $this, 'maybe_render_admin_notices' ), PHP_INT_MAX );

		add_action( 'shutdown', [ $this, 'maybe_translate_medias_in_posts' ], 40 );

		if (
			Option::shouldShowHandleMediaAutoBannerAfterUpgrade() ||
			Option::shouldShowHandleMediaAutoNotice30DaysAfterUpgrade() ||
			$this->should_show_admin_notice_for_elementor_on_mt_homepage()
		) {
			add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_scripts' ) );
		}

		if ( Option::shouldShowHandleMediaAutoBannerAfterUpgrade() || Option::shouldShowHandleMediaAutoNotice30DaysAfterUpgrade() ) {
			add_action( 'wp_ajax_wpml_media_dismiss_should_handle_media_auto_banner', array( $this, 'ajax_dismiss_should_handle_media_auto_banner' ), 10, 0 );
			add_action( 'wp_ajax_wpml_media_dismiss_should_handle_media_auto_notice', array( $this, 'ajax_dismiss_should_handle_media_auto_notice' ), 10, 0 );
		}

		add_action( 'wp_ajax_wpml_media_dismiss_admin_notice_for_elementor_on_mt_homepage_notice', array( $this, 'ajax_dismiss_admin_notice_for_elementor_on_mt_homepage_notice' ), 10, 0 );
	}

	public function enqueue_scripts() {
		$handle = 'wpml-media-admin-notices';

		wp_register_script(
			$handle,
			ICL_PLUGIN_URL . '/res/js/media/admin-notices.js',
			[],
			ICL_SITEPRESS_SCRIPT_VERSION,
			true
		);

		wp_localize_script(
			$handle,
			'wpml_media_admin_notices_data',
			[
				'nonce_wpml_media_dismiss_should_handle_media_auto_banner' => wp_create_nonce( 'wpml_media_dismiss_should_handle_media_auto_banner' ),
				'nonce_wpml_media_dismiss_should_handle_media_auto_notice' => wp_create_nonce( 'wpml_media_dismiss_should_handle_media_auto_notice' ),
				'nonce_wpml_media_dismiss_admin_notice_for_elementor_on_mt_homepage_notice' => wp_create_nonce( 'wpml_media_dismiss_admin_notice_for_elementor_on_mt_homepage_notice' ),
			]
		);

		wp_enqueue_script( $handle );
	}

	public function add_settings_hooks() {
		if ( User::getCurrent() && ( User::canManageTranslations() || User::hasCap( 'wpml_manage_media_translation' ) )
		) {
			add_action('wp_ajax_wpml_media_set_content_defaults', array($this, 'wpml_media_set_content_defaults') );
		}
	}

	private function add_postmeta_hooks() {
		add_action( 'update_postmeta', [ $this, 'record_original_thumbnail_ids_and_sync' ], 10, 4 );
		add_action( 'delete_post_meta', [ $this, 'record_original_thumbnail_ids_and_sync' ], 10, 4 );
	}

	private function withPostMetaFiltersDisabled( callable $callback ) {
		$filter = [ $this, 'record_original_thumbnail_ids_and_sync' ];

		$shouldRestoreFilters = remove_action( 'update_postmeta', $filter, 10 )
			&& remove_action( 'delete_post_meta', $filter, 10 );

		$callback();

		if ( $shouldRestoreFilters ) {
			$this->add_postmeta_hooks();
		}
	}

	private function is_admin_or_xmlrpc() {
		$is_admin  = is_admin();
		$is_xmlrpc = defined( 'XMLRPC_REQUEST' ) && XMLRPC_REQUEST;
		return $is_admin || $is_xmlrpc;
	}

	public function save_attachment_actions( $post_id, $override_always_translate_media = false, $target_languages = null ) {
		if ( $this->is_uploading_media_on_wpml_media_screen() ) {
			return;
		}

		if ( $this->is_uploading_plugin_or_theme() && get_post_type( $post_id ) == 'attachment' ) {
			return;
		}

		$media_language = $this->sitepress->get_language_for_element( $post_id, 'post_attachment' );
		$trid           = false;
		if ( ! empty( $media_language ) ) {
			$trid = $this->sitepress->get_element_trid( $post_id, 'post_attachment' );
		}
		if ( empty( $media_language ) ) {
			$parent_post_sql      = "SELECT p2.ID, p2.post_type FROM {$this->wpdb->posts} p1 JOIN {$this->wpdb->posts} p2 ON p1.post_parent = p2.ID WHERE p1.ID=%d";
			$parent_post_prepared = $this->wpdb->prepare( $parent_post_sql, array( $post_id ) );
			/** @var \stdClass $parent_post */
			$parent_post = $this->wpdb->get_row( $parent_post_prepared );

			if ( $parent_post ) {
				$media_language = $this->sitepress->get_language_for_element( $parent_post->ID, 'post_' . $parent_post->post_type );
			}

			if ( empty( $media_language ) ) {
				$media_language = $this->sitepress->get_admin_language_cookie();
			}
			if ( empty( $media_language ) ) {
				$media_language = $this->sitepress->get_default_language();
			}
		}
		if ( ! empty( $media_language ) ) {
			$this->sitepress->set_element_language_details( $post_id, 'post_attachment', $trid, $media_language );

			$this->save_translated_attachments( $post_id, $override_always_translate_media, $target_languages );
			$this->update_attachment_metadata( $post_id );
		}
	}

	private function is_uploading_media_on_wpml_media_screen() {
		return isset( $_POST['action'] ) && 'wpml_media_save_translation' === $_POST['action'];
	}

	public function wp_generate_attachment_metadata( $metadata, $attachment_id ) {
		if ( $this->is_uploading_media_on_wpml_media_screen() ) {
			return $metadata;
		}

		$this->synchronize_attachment_metadata( $metadata, $attachment_id );

		return $metadata;
	}

	private function update_attachment_metadata( $source_attachment_id ) {
		$original_element_id = $this->sitepress->get_original_element_id( $source_attachment_id, 'post_attachment', false, false, true );
		if ( $original_element_id ) {
			$metadata = wp_get_attachment_metadata( $original_element_id );
			$this->synchronize_attachment_metadata( $metadata, $original_element_id );
		}
	}

	private function synchronize_attachment_metadata( $metadata, $attachment_id ) {
		// Update _wp_attachment_metadata to all translations (excluding the current one)
		$trid = $this->sitepress->get_element_trid( $attachment_id, 'post_attachment' );

		if ( $trid ) {
			$translations = $this->sitepress->get_element_translations( $trid, 'post_attachment', true, true, true );
			foreach ( $translations as $translation ) {
				if ( $translation->element_id != $attachment_id ) {
					$this->update_attachment_texts( $translation );

					/**
					 * Action to allow synchronise additional attachment data with translation.
					 *
					 * @param int    $attachment_id The ID of original attachment.
					 * @param object $translation   The translated attachment.
					 */
					do_action( 'wpml_after_update_attachment_texts', $attachment_id, $translation );

					$attachment_meta_data = get_post_meta( $translation->element_id, '_wp_attachment_metadata' );
					if ( isset( $attachment_meta_data[0]['file'] ) ) {
						continue;
					}

					// Preserve thumbs file names. Otherwise they will be overwritten by the original attachment's thumbs even if they are translated.
					// It happens when the original attachment is trashed or edited.
					if ( isset( $attachment_meta_data[0]['sizes'] ) ) {
						$metadata['sizes'] = $attachment_meta_data[0]['sizes'];
					}

					update_post_meta( $translation->element_id, '_wp_attachment_metadata', $metadata );
					$mime_type = get_post_mime_type( $attachment_id );
					if ( $mime_type ) {
						$this->wpdb->update( $this->wpdb->posts, array( 'post_mime_type' => $mime_type ), array( 'ID' => $translation->element_id ) );
					}
				}
			}
		}
	}

	private function update_attachment_texts( $translation ) {
		if ( ! isset( $_POST['changes'] ) ) {
			return;
		}

		$changes = array( 'ID' => $translation->element_id );

		foreach ( $_POST['changes'] as $key => $value ) {
			switch ( $key ) {
				case 'caption':
					$post = get_post( $translation->element_id );
					if ( ! $post->post_excerpt ) {
						$changes['post_excerpt'] = $value;
					}

					break;

				case 'description':
					$translated_attachment = get_post( $translation->element_id );
					if ( ! $translated_attachment->post_content ) {
						$changes['post_content'] = $value;
					}

					break;

				case 'alt':
					if ( ! get_post_meta( $translation->element_id, '_wp_attachment_image_alt', true ) ) {
						update_post_meta( $translation->element_id, '_wp_attachment_image_alt', $value );
					}

					break;
			}
		}

		remove_action( 'edit_attachment', array( $this, 'save_attachment_actions' ) );
		wp_update_post( $changes );
		add_action( 'edit_attachment', array( $this, 'save_attachment_actions' ) );
	}

	public function save_translated_attachments( $post_id, $override_always_translate_media = false, $target_languages = null ) {
		if ( $this->is_uploading_plugin_or_theme() && get_post_type( $post_id ) == 'attachment' ) {
			return;
		}

		$language_details = $this->sitepress->get_element_language_details( $post_id, 'post_attachment' );
		if ( isset( $language_details->language_code ) ) {
			$this->translate_attachments( $post_id, $language_details->language_code, $override_always_translate_media, $target_languages );
		}
	}

	private function translate_attachments( $attachment_id, $source_language, $override_always_translate_media = false, $target_languages = null ) {
		if ( ! $source_language ) {
			return;
		}

		if ( $override_always_translate_media || ( Obj::prop( 'always_translate_media', Option::getNewContentSettings() ) && ! Option::shouldHandleMediaAuto() ) ) {

			/** @var SitePress $sitepress */
			global $sitepress;

			$original_attachment_id = false;
			$trid                   = $sitepress->get_element_trid( $attachment_id, 'post_attachment' );
			if ( $trid ) {
				$translations                   = $sitepress->get_element_translations( $trid, 'post_attachment', true, true );
				$translated_languages           = [];
				$default_language               = $sitepress->get_default_language();
				$default_language_attachment_id = false;
				foreach ( $translations as $translation ) {
					// Get the default language attachment ID
					if ( $translation->original ) {
						$original_attachment_id = $translation->element_id;
					}
					if ( $translation->language_code == $default_language ) {
						$default_language_attachment_id = $translation->element_id;
					}
					// Store already translated versions
					$translated_languages[] = $translation->language_code;
				}
				// Original attachment is missing
				if ( ! $original_attachment_id ) {
					$attachment = get_post( $attachment_id );
					if ( ! $default_language_attachment_id ) {
						$this->create_duplicate_attachment( $attachment_id, $attachment->post_parent, $default_language );
					} else {
						$sitepress->set_element_language_details( $default_language_attachment_id, 'post_attachment', $trid, $default_language, null );
					}
					// Start over
					$this->translate_attachments( $attachment->ID, $source_language );
				} else {
					// Original attachment is present
					$original = get_post( $original_attachment_id );
					$codes    = array_keys( $sitepress->get_active_languages() );
					if ( is_array( $target_languages ) ) {
						$codes = array_filter(
							$codes,
							function( $code ) use ( $target_languages ) {
								return in_array( $code, $target_languages );
							}
						);
					}

					foreach ( $codes as $code ) {
						// If translation is not present, create it
						if ( ! in_array( $code, $translated_languages ) ) {
							$this->create_duplicate_attachment( $attachment_id, $original->post_parent, $code );
						}
					}
				}
			}
		}

	}

	private function is_uploading_plugin_or_theme() {
		global $action;

		return isset( $action ) && ( $action == 'upload-plugin' || $action == 'upload-theme' );
	}

	public function make_duplicate( $master_post_id, $target_lang, $post_array, $target_post_id ) {
		$translated_attachment_id = false;
		// Get Master Post attachments
		$master_post_attachment_ids_prepared = $this->wpdb->prepare(
			"SELECT ID FROM {$this->wpdb->posts} WHERE post_parent = %d AND post_type = %s",
			array(
				$master_post_id,
				'attachment',
			)
		);
		$master_post_attachment_ids          = $this->wpdb->get_col( $master_post_attachment_ids_prepared );

		if ( $master_post_attachment_ids ) {
			foreach ( $master_post_attachment_ids as $master_post_attachment_id ) {

				$attachment_trid = $this->sitepress->get_element_trid( $master_post_attachment_id, 'post_attachment' );

				if ( $attachment_trid ) {
					// Get attachment translation
					$attachment_translations = $this->sitepress->get_element_translations( $attachment_trid, 'post_attachment' );

					foreach ( $attachment_translations as $attachment_translation ) {
						if ( $attachment_translation->language_code == $target_lang ) {
							$translated_attachment_id = $attachment_translation->element_id;
							break;
						}
					}

					if ( ! $translated_attachment_id ) {
						$translated_attachment_id = $this->create_duplicate_attachment( $master_post_attachment_id, wp_get_post_parent_id( $master_post_id ), $target_lang );
					}

					if ( $translated_attachment_id ) {
						// Set the parent post, if not already set
						$translated_attachment = get_post( $translated_attachment_id );
						if ( $translated_attachment && ! $translated_attachment->post_parent ) {
							$prepared_query = $this->wpdb->prepare(
								"UPDATE {$this->wpdb->posts} SET post_parent=%d WHERE ID=%d",
								array(
									$target_post_id,
									$translated_attachment_id,
								)
							);
							$this->wpdb->query( $prepared_query );
						}
					}
				}
			}
		}

		// Duplicate the featured image.

		$thumbnail_id = get_post_meta( $master_post_id, '_thumbnail_id', true );

		if ( $thumbnail_id ) {

			$thumbnail_trid = $this->sitepress->get_element_trid( $thumbnail_id, 'post_attachment' );

			if ( $thumbnail_trid ) {
				// translation doesn't have a featured image
				$t_thumbnail_id = icl_object_id( $thumbnail_id, 'attachment', false, $target_lang );
				if ( $t_thumbnail_id == null ) {
					$dup_att_id     = $this->create_duplicate_attachment( $thumbnail_id, $target_post_id, $target_lang );
					$t_thumbnail_id = $dup_att_id;
				}

				if ( $t_thumbnail_id != null ) {
					update_post_meta( $target_post_id, '_thumbnail_id', $t_thumbnail_id );
				}
			}
		}

		return $translated_attachment_id;
	}

	/**
	 * @param int            $attachment_id
	 * @param int|false|null $parent_id
	 * @param string         $target_language
	 *
	 * @return int|null
	 */
	public function create_duplicate_attachment( $attachment_id, $parent_id, $target_language ) {
		try {
			$attachment_post = get_post( $attachment_id );
			if ( ! $attachment_post ) {
				throw new WPML_Media_Exception( sprintf( 'Post with id %d does not exist', $attachment_id ) );
			}

			$trid = $this->sitepress->get_element_trid( $attachment_id, WPML_Model_Attachments::ATTACHMENT_TYPE );
			if ( ! $trid ) {
				throw new WPML_Media_Exception( sprintf( 'Attachment with id %s does not contain language information', $attachment_id ) );
			}

			$duplicated_attachment    = $this->attachments_model->find_duplicated_attachment( $trid, $target_language );
			$duplicated_attachment_id = null;
			if ( null !== $duplicated_attachment ) {
				$duplicated_attachment_id = $duplicated_attachment->ID;
			}
			$translated_parent_id = $this->attachments_model->fetch_translated_parent_id( $duplicated_attachment, $parent_id, $target_language );

			if ( null !== $duplicated_attachment ) {
				if ( (int) $duplicated_attachment->post_parent !== (int) $translated_parent_id ) {
					$this->attachments_model->update_parent_id_in_existing_attachment( $translated_parent_id, $duplicated_attachment );
				}
			} else {
				$duplicated_attachment_id = $this->attachments_model->duplicate_attachment( $attachment_id, $target_language, $translated_parent_id, $trid );
			}

			$this->attachments_model->duplicate_post_meta_data( $attachment_id, $duplicated_attachment_id );

			/**
			 * Fires when attachment is duplicated
			 *
			 * @since 4.1.0
			 *
			 * @param int $attachment_id            The ID of the source/original attachment.
			 * @param int $duplicated_attachment_id The ID of the duplicated attachment.
			 */
			do_action( 'wpml_after_duplicate_attachment', $attachment_id, $duplicated_attachment_id );

			return $duplicated_attachment_id;
		} catch ( WPML_Media_Exception $e ) {
			return null;
		}
	}

	public function sync_on_translation_complete( $new_post_id, $fields, $job ) {
		$new_post = get_post( $new_post_id );
		$this->save_post_actions( $new_post_id, $new_post );
	}

	public function record_original_thumbnail_ids_and_sync( $meta_id, $object_id, $meta_key, $meta_value ) {
		if ( '_thumbnail_id' === $meta_key ) {
			$original_thumbnail_id = get_post_meta( $object_id, $meta_key, true );
			if ( $original_thumbnail_id !== $meta_value ) {
				$this->original_thumbnail_ids[ $object_id ] = $original_thumbnail_id;
				$this->sync_post_thumbnail( $object_id, $meta_value ? $meta_value : false );
			}
		}
	}

	/**
	 * We need to create post attachment duplicates in two following cases(if new setting to handle Media is enabled(WPML 4.8+)):
	 * 1) When receiving post translations for the referenced media to have a place where to store translated texts.
	 * 2) When opening page to create or edit page translation in the WordPress Editor(Gutenberg or Legacy) to make the
	 *    media files used in the original posts visible in Media Library popup window and available for the selection.
	 *
	 * Separate queue for posts is required in this method only for WordPress Editor(Gutenberg or Legacy Classical Editor).
	 * It is not required when you are translating post which has attachments with ATE, AT or TEA.
	 * To support case 2) we need to duplicate both referenced and copied attachments when we open add/edit post translation page.
	 * But we should remove duplicates later for the copied attachments as they become redundant after that.
	 *
	 * @param \WP_Screen $screen
	 */
	public function maybe_duplicate_original_post_media( $screen ) {
		if ( ! Option::shouldHandleMediaAuto() ) {
			return;
		}

		$is_media_library_screen     = 'upload' === $screen->base;
		/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
		$is_media_translation_screen = isset( $_GET['page'] ) && 'wpml-media' === $_GET['page'];

		if ( $is_media_library_screen || $is_media_translation_screen ) {
			$this->maybe_clear_duplicated_copied_media_in_posts_queue();
			return;
		}

		$original_post = $this->get_original_post();
		if ( ! $original_post ) {
			return;
		}

		if ( ! class_exists( 'WPML_WP_API' ) ) {
			return;
		}

		$wpml_wp_api = new WPML_WP_API();
		if ( ! $wpml_wp_api->is_new_post_page() && ! $wpml_wp_api->is_post_edit_page() && ! $wpml_wp_api->is_translation_queue_page() ) {
			return;
		}

		$lang = null;
		if ( isset( $_GET['language_code'] ) ) {
			$lang = $_GET['language_code'];
		} else if ( isset( $_GET['language'] ) ) {
			$lang = $_GET['language'];
		} else if ( isset( $_GET['lang'] ) ) {
			$lang = $_GET['lang'];
		}

		if ( ! is_string( $lang ) || strlen( $lang ) < 2 ) {
			return;
		}

		$post_media = $this->post_media_factory->create( $original_post->ID );

		foreach ( $post_media->get_copied_and_referenced__media_ids() as $media_id ) {
			$this->save_attachment_actions( $media_id, true, [ $lang ] );
		}

		$post_media->save_to_posts_queue_with_duplicated_copied_media();
	}

	public function delete_post_media_usages( $post_id ) {
		$maybe_original_post = get_post( $post_id );
		if ( ! $maybe_original_post ) {
			return null;
		}
		$original_post_id = (int) SitePress::get_original_element_id( $maybe_original_post->ID, 'post_' . $maybe_original_post->post_type );

		if ( $original_post_id !== (int) $post_id ) {
			return null;
		}

		$post_media = $this->post_media_factory->create( $original_post_id );
		$post_media->remove_usage_of_media_files_in_post();
	}

	/**
	 * @return WP_Post|null
	 */
	private function get_original_post() {
		/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
		$has_trid = isset( $_GET['trid'] );
		/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
		$has_post = isset( $_GET['post'] );
		/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
		$has_job_id = isset( $_GET['job_id'] );

		$original_post_id = null;

		if ( $has_trid ) {
			/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
			$trid             = intval( $_GET['trid'] );
			$original_post_id = SitePress::get_original_element_id_by_trid( $trid );
		} elseif ( $has_post ) {
			/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
			$maybe_original_post_id = intval( $_GET['post'] );
			$maybe_original_post    = get_post( $maybe_original_post_id );
			if ( ! $maybe_original_post ) {
				return null;
			}
			$original_post_id = (int) SitePress::get_original_element_id( $maybe_original_post_id, 'post_' . $maybe_original_post->post_type );

			// We should duplicate media only when editing post translations and not the original posts.
			if ( $original_post_id === $maybe_original_post_id ) {
				return null;
			}
		} elseif ( $has_job_id ) {
			/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
			$job_id = intval( $_GET['job_id'] );
			$job    = Jobs::get( $job_id );

			if ( ! is_object( $job ) ) {
				return null;
			}

			$original_post = TranslationRecords::getSourceByTrid( $job->trid );
			if ( ! is_object( $original_post ) ) {
				return null;
			}

			$original_post_id = $original_post->element_id;
		}

		if ( ! is_numeric( $original_post_id ) ) {
			return null;
		}

		return get_post( (int) $original_post_id );
	}

	private function maybe_clear_duplicated_copied_media_in_posts_queue() {
		$post_media = null;
		$queue      = $this->sitepress->get_setting( PostWithMediaFiles::POSTS_QUEUE_WITH_DUPLICATED_COPIED_MEDIA_SETTING, array() );
		foreach ( $queue as $post_id ) {
			$post_media = $this->post_media_factory->create( $post_id );
			$post_media->delete_duplicated_copied_media();
		}
		if ( $post_media ) {
			$post_media->clear_posts_queue_with_duplicated_copied_media();
		}
	}

	public function woocommerce_extract_media_ids_from_post_content_and_meta( $post, $update ) {
		$post = get_post( $post );
		$this->extract_media_ids_from_post_content_and_meta( $post, $update );
	}

	// phpcs:ignore Generic.CodeAnalysis.UnusedFunctionParameter.FoundAfterLastUsed
	public function extract_media_ids_from_post_content_and_meta( $post, $update, $post_before = null ) {
		if ( is_int( $post ) ) {
			$post = get_post( $post );
		}

		if ( 'attachment' === $post->post_type ) {
			return;
		}

		if ( (int) $post->ID === 0) {
			return;
		}

		if ( ! $this->is_valid_post_to_process( $post->ID, $post->post_type, $post->post_status, false ) ) {
			return;
		}

		if ( ! $this->is_original( $post ) ) {
			return;
		}

		$post_media = $this->post_media_factory->create( $post->ID );
		$post_media->extract_and_save_media_ids();
	}

	private function is_original( $post ) {
		return (int) $post->ID === (int) $this->sitepress->get_original_element_id( $post->ID, 'post_' . $post->post_type, false, false, false, true );
	}

	/**
	 * @param int     $pidd
	 * @param WP_Post $post
	 */
	function save_post_actions( $pidd, $post ) {
		if ( ! $post ) {
			return;
		}

		if ( $post->post_type !== 'attachment' && $post->post_status !== 'auto-draft' ) {
			$this->sync_attachments( $pidd, $post );

			if ( ! $this->is_original( $post ) ) {
				$this->save_post_queue[] = $post;
			}
		}

		if ( $post->post_type === 'attachment' ) {
			$metadata      = wp_get_attachment_metadata( $post->ID );
			$attachment_id = $pidd;
			if ( $metadata ) {
				$this->synchronize_attachment_metadata( $metadata, $attachment_id );
			}
		}
	}

	function maybe_translate_medias_in_posts() {
		foreach ( $this->save_post_queue as $post ) {
			$all_meta = get_post_meta( $post->ID );
			$data     = [];
			$lang     = $this->sitepress->get_language_for_element( $post->ID, 'post_' . $post->post_type );

			foreach ( $all_meta as $key => $value ) {
				if ( strpos( $key, '_bricks_' ) === 0 ) {
					$item = maybe_unserialize( $value[0] );
					if ( ! is_array( $item ) ) {
						continue;
					}

					$this->translate_bricks_media( $item, $lang );
					update_post_meta( $post->ID, $key, $item );
				}

				if ( strpos( $key, 'panels_data' ) === 0 ) {
					$item = maybe_unserialize( $value[0] );
					if ( ! is_array( $item ) ) {
						continue;
					}

					$this->translate_siteorigin_media( $item, $lang );
					update_post_meta( $post->ID, $key, $item );
				}
			}
		}
	}

	private function translate_bricks_media( &$data, $lang ) {
		$iterator = function( &$node ) use ( &$iterator, $lang ) {
			if ( ! is_array( $node ) ) {
				return;
			}

			if ( isset( $node['settings']['image']['id'] ) ) {
				$node['settings']['image']['id'] = $this->get_translated_attachment_id( $node['settings']['image']['id'], $lang );
			}

			if ( isset( $node['settings']['items']['images'] ) && is_array( $node['settings']['items']['images'] ) ) {
				foreach ( $node['settings']['items']['images'] as &$image ) {
					if ( isset( $image['id'] ) ) {
						$image['id'] = $this->get_translated_attachment_id( $image['id'], $lang );
					}
				}
			}

			if ( isset( $node['settings']['_background']['image']['id'] ) ) {
				$node['settings']['_background']['image']['id'] = $this->get_translated_attachment_id( $node['settings']['_background']['image']['id'], $lang );
			}

			foreach ( $node as &$value ) {
				if ( is_array( $value ) ) {
					$iterator( $value );
				}
			}
		};

		$iterator( $data );
	}

	private function translate_siteorigin_media( &$data, $lang ) {
		$iterator = function( &$node ) use ( &$iterator, $lang ) {
			if ( ! is_array( $node ) ) {
				return;
			}

			if ( isset( $node['option_name'] ) && $node['option_name'] === 'widget_sow-image' && isset( $node['image'] ) && is_numeric( $node['image'] ) ) {
				$is_custom_alt_setup = isset( $node['alt'] ) && is_string( $node['alt'] ) && strlen( $node['alt'] ) > 0;
				if ( ! $is_custom_alt_setup ) {
					$node['image'] = $this->get_translated_attachment_id( $node['image'], $lang );
				}
			}

			if ( isset( $node['option_name'] ) && $node['option_name'] === 'widget_sow-slider' && isset( $node['frames'] ) && is_array( $node['frames'] ) ) {
				foreach ( $node['frames'] as &$image ) {
					if ( isset( $image['foreground_image'] ) && is_numeric( $image['foreground_image'] ) ) {
						$image['foreground_image'] = $this->get_translated_attachment_id( $image['foreground_image'], $lang );
					}
					if ( isset( $image['background_image'] ) && is_numeric( $image['background_image'] ) ) {
						$image['background_image'] = $this->get_translated_attachment_id( $image['background_image'], $lang );
					}
				}
			}

			foreach ( $node as &$value ) {
				if ( is_array( $value ) ) {
					$iterator( $value );
				}
			}
		};

		$iterator( $data );
	}

	private function get_translated_attachment_id( $id, $lang ) {
		$key = $id . $lang;

		if ( ! array_key_exists( $key, $this->translated_posts ) ) {
			$factory = new WPML_Translation_Element_Factory( $this->sitepress );

			$this->translated_posts[ $key ] = null;
			$element                        = $factory->create_post( $id );
			$translation                    = $element->get_translation( $lang, true );

			if ( $translation ) {
				$this->translated_posts[ $key ] = $translation->get_wp_object();
			}
		}

		return is_object( $this->translated_posts[ $key ] ) ? $this->translated_posts[ $key ]->ID : $id;
	}

	/**
	 * @param int     $pidd
	 * @param string  $post_type
	 * @param string  $post_status
	 * @param boolean $check_if_is_translated_type
	 *
	 * @return boolean
	 */
	private function is_valid_post_to_process($pidd, $post_type, $post_status, bool $check_if_is_translated_type = true ) {
		$is_invalid = (
			( $check_if_is_translated_type && ! $this->sitepress->is_translated_post_type( $post_type ) )
			// phpcs:ignore WordPress.Security.NonceVerification.Missing, WordPress.Security.NonceVerification.Recommended
			|| isset( $_POST['autosave'] )
			// phpcs:ignore WordPress.Security.NonceVerification.Missing, WordPress.Security.NonceVerification.Recommended
			|| ( isset( $_POST['post_ID'] ) && (int) $_POST['post_ID'] !== (int) $pidd )
			// phpcs:ignore WordPress.Security.NonceVerification.Missing, WordPress.Security.NonceVerification.Recommended
			|| ( isset( $_POST['post_type'] ) && 'revision' === $_POST['post_type'] )
			|| 'revision' === $post_type
			|| get_post_meta( $pidd, '_wp_trash_meta_status', true )
			// phpcs:ignore WordPress.Security.NonceVerification.Missing, WordPress.Security.NonceVerification.Recommended
			|| ( isset( $_GET['action'] ) && 'restore' === $_GET['action'] )
			|| 'auto-draft' === $post_status
		);

		return ! $is_invalid;
	}

	/**
	 * @param int     $pidd
	 * @param WP_Post $post
	 */
	function sync_attachments( $pidd, $post ) {
		if ( $post->post_type == 'attachment' || $post->post_status == 'auto-draft' ) {
			return;
		}

		$posts_prepared                  = $this->wpdb->prepare( "SELECT post_type, post_status FROM {$this->wpdb->posts} WHERE ID = %d", array( $pidd ) );
		list( $post_type, $post_status ) = $this->wpdb->get_row( $posts_prepared, ARRAY_N );

		// checking - if translation and not saved before
		if ( isset( $_GET['trid'] ) && ! empty( $_GET['trid'] ) && $post_status == 'auto-draft' ) {

			// get source language
			if ( isset( $_GET['source_lang'] ) && ! empty( $_GET['source_lang'] ) ) {
				$src_lang = $_GET['source_lang'];
			} else {
				$src_lang = $this->sitepress->get_default_language();
			}

			// get source id
			$src_id_prepared = $this->wpdb->prepare( "SELECT element_id FROM {$this->wpdb->prefix}icl_translations WHERE trid=%d AND language_code=%s", array( $_GET['trid'], $src_lang ) );
			$src_id          = $this->wpdb->get_var( $src_id_prepared );

			// delete exist auto-draft post media
			$results_prepared = $this->wpdb->prepare( "SELECT p.id FROM {$this->wpdb->posts} AS p LEFT JOIN {$this->wpdb->posts} AS p1 ON p.post_parent = p1.id WHERE p1.post_status = %s", array( 'auto-draft' ) );
			$results          = $this->wpdb->get_results( $results_prepared, ARRAY_A );
			$attachments      = array();
			if ( ! empty( $results ) ) {
				foreach ( $results as $result ) {
					$attachments[] = $result['id'];
				}
				if ( ! empty( $attachments ) ) {
					$in_attachments  = wpml_prepare_in( $attachments, '%d' );
					$delete_prepared = "DELETE FROM {$this->wpdb->posts} WHERE id IN (" . $in_attachments . ')';
					$this->wpdb->query( $delete_prepared );
					$delete_prepared = "DELETE FROM {$this->wpdb->postmeta} WHERE post_id IN (" . $in_attachments . ')';
					$this->wpdb->query( $delete_prepared );
				}
			}

			// checking - if set duplicate media
			if ( $src_id && Option::shouldDuplicateMedia( (int) $src_id ) ) {
				// duplicate media before first save
				$this->duplicate_post_attachments( $pidd, $_GET['trid'], $src_lang, $this->sitepress->get_language_for_element( $pidd, 'post_' . $post_type ) );
			}
		}

		// exceptions
		if ( ! $this->is_valid_post_to_process( $pidd, $post_type, $post_status ) ) {
			return;
		}

		if ( isset( $_POST['icl_trid'] ) ) {
			$icl_trid = $_POST['icl_trid'];
		} else {
			// get trid from database.
			$icl_trid_prepared = $this->wpdb->prepare( "SELECT trid FROM {$this->wpdb->prefix}icl_translations WHERE element_id=%d AND element_type = %s", array( $pidd, 'post_' . $post_type ) );
			$icl_trid          = $this->wpdb->get_var( $icl_trid_prepared );
		}

		if ( $icl_trid ) {
			$language_details = $this->sitepress->get_element_language_details( $pidd, 'post_' . $post_type );

			// In some cases the sitepress cache doesn't get updated (e.g. when posts are created with wp_insert_post()
			// Only in this case, the sitepress cache will be cleared so we can read the element language details
			if ( ! $language_details ) {
				$this->sitepress->get_translations_cache()->clear();
				$language_details = $this->sitepress->get_element_language_details( $pidd, 'post_' . $post_type );
			}
			if ( $language_details ) {
				$this->duplicate_post_attachments( $pidd, $icl_trid, $language_details->source_language_code, $language_details->language_code );
			}
		}
	}

	/**
	 * @param int      $post_id
	 * @param int|null $request_post_thumbnail_id
	 */
	public function sync_post_thumbnail( $post_id, $request_post_thumbnail_id = null ) {

		if ( $post_id && Option::shouldDuplicateFeatured( $post_id ) || Option::shouldHandleMediaAuto() ) {

			if ( null === $request_post_thumbnail_id ) {
				$request_post_thumbnail_id = filter_input(
					INPUT_POST,
					'thumbnail_id',
					FILTER_SANITIZE_NUMBER_INT,
					FILTER_NULL_ON_FAILURE
				);

				$thumbnail_id = $request_post_thumbnail_id ?
					$request_post_thumbnail_id :
					get_post_meta( $post_id, '_thumbnail_id', true );
			} else {
				$thumbnail_id = $request_post_thumbnail_id;
			}

			$trid         = $this->sitepress->get_element_trid( $post_id, 'post_' . get_post_type( $post_id ) );
			$translations = $this->sitepress->get_element_translations( $trid, 'post_' . get_post_type( $post_id ) );

			// Check if it is original.
			$is_original = false;
			foreach ( $translations as $translation ) {
				if ( 1 === (int) $translation->original && (int) $translation->element_id === $post_id ) {
					$is_original = true;
				}
			}

			if ( $is_original ) {
				foreach ( $translations as $translation ) {
					if ( ! $translation->original && $translation->element_id ) {
						if ( $this->are_post_thumbnails_still_in_sync( $post_id, $thumbnail_id, $translation ) ) {
							if ( ! $thumbnail_id || - 1 === (int) $thumbnail_id ) {
								$this->withPostMetaFiltersDisabled(
									function () use ( $translation ) {
										delete_post_meta( $translation->element_id, '_thumbnail_id' );
									}
								);
							} else {
								$translated_thumbnail_id = wpml_object_id_filter(
									$thumbnail_id,
									'attachment',
									false,
									$translation->language_code
								);

								$id = get_post_meta( $translation->element_id, '_thumbnail_id', true );
								if ( (int) $id !== $translated_thumbnail_id ) {
									$this->withPostMetaFiltersDisabled(
										function () use ( $translation, $translated_thumbnail_id ) {
											update_post_meta( $translation->element_id, '_thumbnail_id', $translated_thumbnail_id );
										}
									);
								}
							}
						}
					}
				}
			}
		}
	}

	protected function are_post_thumbnails_still_in_sync( $source_id, $source_thumbnail_id, $translation ) {

		$translation_thumbnail_id = get_post_meta( $translation->element_id, '_thumbnail_id', true );

		if ( isset( $this->original_thumbnail_ids[ $source_id ] ) ) {
			if ( $this->original_thumbnail_ids[ $source_id ] === $translation_thumbnail_id ) {
				return true;
			}

			return $this->are_translations_of_each_other(
				$this->original_thumbnail_ids[ $source_id ],
				$translation_thumbnail_id
			);
		} else {
			return $this->are_translations_of_each_other(
				$source_thumbnail_id,
				$translation_thumbnail_id
			);
		}
	}

	private function are_translations_of_each_other( $post_id_1, $post_id_2 ) {
		return $this->sitepress->get_element_trid( $post_id_1, 'post_' . get_post_type( $post_id_1 ) ) ===
			$this->sitepress->get_element_trid( $post_id_2, 'post_' . get_post_type( $post_id_2 ) );
	}

	function duplicate_post_attachments( $pidd, $icl_trid, $source_lang = null, $lang = null ) {
		$wpdb                           = $this->wpdb;
		$pidd                           = ( is_numeric( $pidd ) ) ? (int) $pidd : null;
		$request_post_icl_ajx_action    = filter_input( INPUT_POST, 'icl_ajx_action', FILTER_SANITIZE_FULL_SPECIAL_CHARS, FILTER_NULL_ON_FAILURE );
		$request_post_icl_post_language = filter_input( INPUT_POST, 'icl_post_language', FILTER_SANITIZE_FULL_SPECIAL_CHARS, FILTER_NULL_ON_FAILURE );
		$request_post_post_id           = filter_input( INPUT_POST, 'post_id', FILTER_SANITIZE_NUMBER_INT, FILTER_NULL_ON_FAILURE );

		if ( $icl_trid == '' ) {
			return;
		}

		if ( ! $source_lang ) {
			$source_lang_prepared = $this->wpdb->prepare( "SELECT source_language_code FROM {$this->wpdb->prefix}icl_translations WHERE element_id = %d AND trid=%d", array( $pidd, $icl_trid ) );
			$source_lang          = $this->wpdb->get_var( $source_lang_prepared );
		}

		// exception for making duplicates. language info not set when this runs and creating the duplicated posts 1/3
		if ( $request_post_icl_ajx_action == 'make_duplicates' && $request_post_icl_post_language ) {
			$source_lang_prepared = $this->wpdb->prepare(
				"SELECT language_code FROM {$this->wpdb->prefix}icl_translations
													 WHERE element_id = %d AND trid = %d",
				array( $request_post_post_id, $icl_trid )
			);
			$source_lang          = $this->wpdb->get_var( $source_lang_prepared );
			$lang                 = $request_post_icl_post_language;

		}

		if ( $source_lang == null || $source_lang == '' ) {
			// This is the original see if we should copy to translations
			if ( Option::shouldDuplicateMedia( $pidd ) || Option::shouldDuplicateFeatured( $pidd ) || Option::shouldHandleMediaAuto() ) {
				$active_language_codes  = array_keys( $this->sitepress->get_active_languages() );
				$lang_codes_placeholder = implode( ',', array_fill( 0, count( $active_language_codes ), '%s' ) );

				$translations = $wpdb->get_col(
					$wpdb->prepare(
					// phpcs:disable WordPress.DB.PreparedSQL.InterpolatedNotPrepared
						"SELECT element_id FROM {$wpdb->prefix}icl_translations WHERE trid = %d AND language_code IN ( $lang_codes_placeholder )",
						array_merge( [ $icl_trid ], $active_language_codes )
					)
				);
				$translations = array_map( 'intval', $translations );

				$source_attachments = $wpdb->get_col(
					$wpdb->prepare(
						'SELECT ID FROM ' . $wpdb->posts . ' WHERE post_parent = %d AND post_type = %s',
						array( $pidd, 'attachment' )
					)
				);
				$source_attachments = array_map( 'intval', $source_attachments );

				$all_element_ids           = [];
				$attachments_by_element_id = [];
				foreach ( $translations as $element_id ) {
					if ( $element_id && $element_id !== $pidd ) {
						$all_element_ids[]                        = $element_id;
						$attachments_by_element_id[ $element_id ] = [];
					}
				}
				$all_attachments = [];
				if ( count( $all_element_ids ) > 0 ) {
					$all_attachments = $wpdb->get_results(
						$wpdb->prepare(
						// phpcs:disable WordPress.DB.PreparedSQL.NotPrepared
							'SELECT ID, post_parent AS element_id FROM ' . $wpdb->posts . ' WHERE post_parent IN (' . wpml_prepare_in( $all_element_ids ) . ') AND post_type = %s',
							array( 'attachment' )
						),
						ARRAY_A
					);
				}
				foreach ( $all_attachments as $attachment ) {
					$attachments_by_element_id[ (int) $attachment['element_id'] ][] = (int) $attachment['ID'];
				}

				foreach ( $translations as $element_id ) {
					if ( $element_id && $element_id !== $pidd ) {
						$lang_prepared = $this->wpdb->prepare( "SELECT language_code FROM {$this->wpdb->prefix}icl_translations WHERE element_id = %d AND trid = %d", array( $element_id, $icl_trid ) );
						$lang          = $this->wpdb->get_var( $lang_prepared );

						$should_duplicate_featured = Option::shouldDuplicateFeatured( $element_id ) || Option::shouldHandleMediaAuto();

						if ( $should_duplicate_featured ) {
							$attachments                           = $attachments_by_element_id[ $element_id ];
							$has_missing_translation_attachment_id = false;

							foreach ( $attachments as $attachment_id ) {
								if ( ! icl_object_id( $attachment_id, 'attachment', false, $lang ) ) {
									$has_missing_translation_attachment_id = true;
									break;
								}
							}

							$source_attachment_ids = $has_missing_translation_attachment_id ? $source_attachments : [];

							foreach ( $source_attachment_ids as $source_attachment_id ) {
								$this->create_duplicate_attachment_not_static( $source_attachment_id, $element_id, $lang );
							}
						}

						$translation_thumbnail_id = get_post_meta( $element_id, '_thumbnail_id', true );
						if ( $should_duplicate_featured && empty( $translation_thumbnail_id ) ) {
							$thumbnail_id = get_post_meta( $pidd, '_thumbnail_id', true );
							if ( $thumbnail_id ) {
								$t_thumbnail_id = icl_object_id( $thumbnail_id, 'attachment', false, $lang );
								if ( $t_thumbnail_id == null ) {
									$dup_att_id     = $this->create_duplicate_attachment_not_static( $thumbnail_id, $element_id, $lang );
									$t_thumbnail_id = $dup_att_id;
								}

								if ( $t_thumbnail_id != null ) {
									update_post_meta( $element_id, '_thumbnail_id', $t_thumbnail_id );
								}
							}
						}
					}
				}
			}
		} else {
			// This is a translation.

			// exception for making duplicates. language info not set when this runs and creating the duplicated posts 2/3
			if ( $request_post_icl_ajx_action === 'make_duplicates' ) {
				$source_id = $request_post_post_id;
			} else {
				$source_id_prepared = $this->wpdb->prepare( "SELECT element_id FROM {$this->wpdb->prefix}icl_translations WHERE language_code = %s AND trid = %d", array( $source_lang, $icl_trid ) );
				$source_id          = $this->wpdb->get_var( $source_id_prepared );
			}

			if ( ! $lang ) {
				$lang_prepared = $this->wpdb->prepare( "SELECT language_code FROM {$this->wpdb->prefix}icl_translations WHERE element_id = %d AND trid = %d", array( $pidd, $icl_trid ) );
				$lang          = $this->wpdb->get_var( $lang_prepared );
			}

			// exception for making duplicates. language info not set when this runs and creating the duplicated posts 3/3
			if ( $request_post_icl_ajx_action === 'make_duplicates' ) {
				$duplicate = Option::shouldDuplicateMedia( $source_id );
			} else {
				$duplicate = Option::shouldDuplicateMedia( $pidd, false );
				if ( $duplicate === null ) {
					// check the original state
					$duplicate = Option::shouldDuplicateMedia( $source_id );
				}
			}

			$copied_media_ids     = [];
			$referenced_media_ids = [];

			if ( Option::shouldHandleMediaAuto() ) {
				$duplicate = true;
				if ( is_numeric( $source_id ) ) {
					$post_media           = $this->post_media_factory->create( $source_id );
					$copied_media_ids     = $post_media->get_copied_media_ids();
					$referenced_media_ids = $post_media->get_referenced_media_ids();
				}
			}

			if ( $duplicate ) {
				$source_attachments_prepared = $this->wpdb->prepare( "SELECT ID FROM {$this->wpdb->posts} WHERE post_parent = %d AND post_type = %s", array( $source_id, 'attachment' ) );
				$source_attachments          = $this->wpdb->get_col( $source_attachments_prepared );

				foreach ( $source_attachments as $source_attachment_id ) {
					$translation_attachment_id = icl_object_id( $source_attachment_id, 'attachment', false, $lang );

					if ( ! $translation_attachment_id ) {
						if (
							Option::shouldHandleMediaAuto() &&
							in_array( $source_attachment_id, $copied_media_ids ) &&
							! in_array( $source_attachment_id, $referenced_media_ids )
						) {
							continue;
						}

						self::create_duplicate_attachment( $source_attachment_id, $pidd, $lang );
					} else {
						$translated_attachment = get_post( $translation_attachment_id );
						if ( $translated_attachment && ! $translated_attachment->post_parent ) {
							$translated_attachment->post_parent = $pidd;
							/** @phpstan-ignore-next-line (WP doc issue) */
							wp_update_post( $translated_attachment );
						}
					}
				}
			}

			$featured = Option::shouldDuplicateFeatured( $pidd, false );
			if ( $featured === null ) {
				// check the original state
				$featured = Option::shouldDuplicateFeatured( $source_id );
			}
			if ( Option::shouldHandleMediaAuto() ) {
				$featured = true;
			}

			$translation_thumbnail_id = get_post_meta( $pidd, '_thumbnail_id', true );
			if ( $featured && empty( $translation_thumbnail_id ) ) {
				$thumbnail_id = get_post_meta( $source_id, '_thumbnail_id', true );
				if ( $thumbnail_id ) {
					$t_thumbnail_id = icl_object_id( $thumbnail_id, 'attachment', false, $lang );
					if ( $t_thumbnail_id == null ) {
						$dup_att_id     = self::create_duplicate_attachment( $thumbnail_id, $pidd, $lang );
						$t_thumbnail_id = $dup_att_id;
					}

					if ( $t_thumbnail_id != null ) {
						update_post_meta( $pidd, '_thumbnail_id', $t_thumbnail_id );
					}
				}
			}
		}

	}

	/**
	 * @param int    $source_attachment_id
	 * @param int    $pidd
	 * @param string $lang
	 *
	 * @return int|null|WP_Error
	 */
	public function create_duplicate_attachment_not_static( $source_attachment_id, $pidd, $lang ) {
		return self::create_duplicate_attachment( $source_attachment_id, $pidd, $lang );
	}

	private function duplicate_featured_images( $limit = 0, $offset = 0 ) {
		global $wpdb;

		list( $thumbnails, $processed ) = $this->get_post_thumbnail_map( $limit, $offset );

		if ( sizeof( $thumbnails ) ) {
			// Posts IDs with found featured images
			$post_ids       = wpml_prepare_in( array_keys( $thumbnails ), '%d' );
			$posts_prepared = "SELECT ID, post_type FROM {$wpdb->posts} WHERE ID IN ({$post_ids})";
			$posts          = $wpdb->get_results( $posts_prepared );
			foreach ( $posts as $post ) {
				$this->duplicate_featured_image_in_post( $post, $thumbnails );
			}
		}

		return $processed;
	}

	/**
	 * @param int $limit
	 * @param int $offset Offset to use for getting thumbnails. Default: 0.
	 *
	 * @return array
	 */
	public function get_post_thumbnail_map( $limit = 0, $offset = 0 ) {
		global $wpdb;

		$featured_images_sql = "SELECT * FROM {$wpdb->postmeta} WHERE meta_key = '_thumbnail_id' ORDER BY `meta_id`";

		if ( $limit > 0 ) {
			$featured_images_sql .= $wpdb->prepare( ' LIMIT %d, %d', $offset, $limit );
		}

		$featured_images = $wpdb->get_results( $featured_images_sql );
		$processed       = count( $featured_images );

		$thumbnails = array();
		foreach ( $featured_images as $featured ) {
			$thumbnails[ $featured->post_id ] = $featured->meta_value;
		}

		return array( $thumbnails, $processed );
	}

	/**
	 * @param \stdClass $post       contains properties `ID` and `post_type`
	 * @param array     $thumbnails a map of post ID => thumbnail ID
	 */
	public function duplicate_featured_image_in_post( $post, $thumbnails = array() ) {
		global $wpdb, $sitepress;

		$row_prepared = $wpdb->prepare(
			"SELECT trid, source_language_code
												FROM {$wpdb->prefix}icl_translations
												WHERE element_id=%d
													AND element_type = %s",
			array( $post->ID, 'post_' . $post->post_type )
		);
		$row          = $wpdb->get_row( $row_prepared );
		if ( $row && $row->trid && ( $row->source_language_code == null || $row->source_language_code == '' ) ) {

			$translations = $sitepress->get_element_translations( $row->trid, 'post_' . $post->post_type );
			foreach ( $translations as $translation ) {

				if ( $translation->element_id != $post->ID ) {

					$translation_thumbnail_id = get_post_meta( $translation->element_id, '_thumbnail_id', true );
					if ( empty( $translation_thumbnail_id ) ) {
						if ( ! in_array( $translation->element_id, array_keys( $thumbnails ) ) ) {

							// translation doesn't have a featured image
							$t_thumbnail_id = icl_object_id( $thumbnails[ $post->ID ], 'attachment', false, $translation->language_code );
							if ( $t_thumbnail_id == null ) {
								$dup_att_id     = self::create_duplicate_attachment( $thumbnails[ $post->ID ], $translation->element_id, $translation->language_code );
								$t_thumbnail_id = $dup_att_id;
							}

							if ( $t_thumbnail_id != null ) {
								update_post_meta( $translation->element_id, '_thumbnail_id', $t_thumbnail_id );
							}
						} elseif ( $thumbnails[ $post->ID ] ) {
							update_post_meta( $translation->element_id, '_thumbnail_id', $thumbnails[ $post->ID ] );
						}
					}
				}
			}
		}
	}

	public function ajax_batch_duplicate_featured_images() {

		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_duplicate_featured_images' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$featured_images_left = array_key_exists( 'featured_images_left', $_POST ) && is_numeric( $_POST['featured_images_left'] )
			? (int) $_POST['featured_images_left']
			: null;

		return $this->batch_duplicate_featured_images( true, $featured_images_left );
	}

	public function batch_duplicate_featured_images( $outputResult = true, $featured_images_left = null ) {
		// Use $featured_images_left if it's a number otherwise proceed with null.
		$featured_images_left = is_numeric( $featured_images_left ) ? (int) $featured_images_left : null;

		if ( null === $featured_images_left ) {
			$featured_images_left = $this->get_featured_images_total_number();
		}

		// Use 10 as limit or what's left if there are less than 10 images left to proceed.
		$limit = $featured_images_left < 10 ? $featured_images_left : 10;

		// Duplicate batch of feature images.
		$processed = $this->duplicate_featured_images( $limit, $featured_images_left - $limit );

		// Response result.
		$response = array( 'left' => max( $featured_images_left - $processed, 0 ) );
		if ( $response['left'] ) {
			$response['message'] = sprintf( __( 'Duplicating featured content: %d left. Stay here until complete. May take a few minutes.', 'sitepress' ), $response['left'] );
		} else {
			$response['message'] = sprintf( __( 'Duplicating featured content: 0 left. Stay here until complete. May take a few minutes.', 'sitepress' ), $response['left'] );
		}

		if ( $outputResult ) {
			wp_send_json( $response );
		}
		return $response['left'];
	}

	/**
	 * Returns the total number of Featured Images.
	 *
	 * @return int
	 */
	private function get_featured_images_total_number() {
		$wpdb = $this->wpdb; // Makes Codesniffer interpret the following correctly.

		return (int) $wpdb->get_var(
			"SELECT COUNT(*)
			FROM {$wpdb->postmeta}
			WHERE meta_key = '_thumbnail_id'"
		);
	}

	public function ajax_batch_duplicate_media() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_duplicate_media' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		return $this->batch_duplicate_media();
	}

	public function batch_duplicate_media( $outputResult = true ) {
		$limit    = 10;
		$response = array();

		$count_sql = $this->wpdb->prepare(
			"
			SELECT COUNT(*) 
				 FROM {$this->wpdb->posts} p1
				 WHERE post_type = %s
				 AND ID NOT IN (
					 SELECT post_id FROM {$this->wpdb->postmeta} WHERE meta_key = %s
				 )
			",
			array( 'attachment', 'wpml_media_processed' )
		);
		$found     = (int) $this->wpdb->get_var( $count_sql );

		$attachments_prepared = $this->wpdb->prepare(
			"
			SELECT p1.ID, p1.post_parent 
				 FROM {$this->wpdb->posts} p1
				 WHERE post_type = %s
				 AND ID NOT IN (
					 SELECT post_id FROM {$this->wpdb->postmeta} WHERE meta_key = %s
				 )
				 ORDER BY p1.ID ASC LIMIT %d
			",
			array( 'attachment', 'wpml_media_processed', $limit )
		);
		$attachments          = $this->wpdb->get_results( $attachments_prepared );

		if ( $attachments ) {
			foreach ( $attachments as $attachment ) {
				$this->create_duplicated_media( $attachment );
			}
		}

		$response['left'] = max( $found - $limit, 0 );
		if ( $response['left'] ) {
			$response['message'] = sprintf( __( 'Duplicating content: %d left. Stay here until complete. May take a few minutes.', 'sitepress' ), $response['left'] );
		} else {
			$response['message'] = sprintf( __( 'Duplicating content: 0 left. Stay here until complete. May take a few minutes.', 'sitepress' ), $response['left'] );
		}

		if ( $outputResult ) {
			wp_send_json( $response );
		}
		return $response['left'];

	}

	private function get_batch_translate_limit( $activeLanguagesCount ) {
		global $sitepress;

		$limit = $sitepress->get_wp_api()->constant( 'WPML_MEDIA_BATCH_LIMIT' );
		$limit = $limit ?: ceil( 100 / max( $activeLanguagesCount - 1, 1 ) );

		return max( $limit, 1 );
	}

	public function ajax_batch_translate_media() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_translate_media' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		return $this->batch_translate_media();
	}

	public function batch_translate_media( $outputResult = true ) {
		$response = [];

		$activeLanguages      = $this->sitepress->get_active_languages();
		$activeLanguagesCount = count( $activeLanguages );
		$placeholders         = implode( ',', array_fill( 0, $activeLanguagesCount, '%s' ) );
		$limit                = $this->get_batch_translate_limit( $activeLanguagesCount );

		$count_sql = $this->wpdb->prepare(
			"
			SELECT COUNT(*) FROM (
					SELECT p1.ID
					FROM {$this->wpdb->prefix}icl_translations t
					INNER JOIN {$this->wpdb->posts} p1
						ON t.element_id = p1.ID AND p1.post_type = 'attachment'
					LEFT JOIN {$this->wpdb->prefix}icl_translations tt
						ON t.trid = tt.trid
					WHERE t.element_type = 'post_attachment'
						AND t.source_language_code IS NULL
						AND tt.language_code IN ($placeholders)
					GROUP BY p1.ID, p1.post_parent
					HAVING COUNT(tt.language_code) < %d
				) AS count_subquery
			",
			array_merge( array_keys( $activeLanguages ), array( $activeLanguagesCount ) )
		);
		$found     = (int) $this->wpdb->get_var( $count_sql );

		// phpcs:ignore WordPress.DB.PreparedSQLPlaceholders.ReplacementsWrongNumber
		$sql         = $this->wpdb->prepare(
			"
			SELECT p1.ID, p1.post_parent
				FROM {$this->wpdb->prefix}icl_translations t
				INNER JOIN {$this->wpdb->posts} p1
					ON t.element_id = p1.ID AND p1.post_type = 'attachment'
				LEFT JOIN {$this->wpdb->prefix}icl_translations tt
					ON t.trid = tt.trid
				WHERE t.element_type = 'post_attachment'
					AND t.source_language_code IS NULL
					AND tt.language_code IN ($placeholders)
				GROUP BY p1.ID, p1.post_parent
				HAVING COUNT(tt.language_code) < %d
				LIMIT %d
    		",
			array_merge( array_keys( $activeLanguages ), array( $activeLanguagesCount, $limit ) )
		);
		$attachments = $this->wpdb->get_results( $sql );

		if ( $attachments ) {
			foreach ( $attachments as $attachment ) {
				$lang = $this->sitepress->get_element_language_details( $attachment->ID, 'post_attachment' );
				$this->translate_attachments( $attachment->ID, ( is_object( $lang ) && property_exists( $lang, 'language_code' ) ) ? $lang->language_code : null, true );
			}
		}

		$response['left'] = max( $found - $limit, 0 );
		if ( $response['left'] ) {
			$response['message'] = sprintf( esc_html__( 'Duplicating content: %d left. Stay here until complete. May take a few minutes.', 'sitepress' ), $response['left'] );
		} else {
			$response['message'] = __( 'Duplicating content: 0 left. Stay here until complete. May take a few minutes.', 'sitepress' );
		}

		if ( $outputResult ) {
			wp_send_json( $response );
		}

		return $response['left'];
	}

	public function batch_set_initial_language() {

		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_set_initial_language' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$default_language = $this->sitepress->get_default_language();
		$limit            = 10;

		$response  = array();
		$count_sql = $this->wpdb->prepare(
			"
			SELECT COUNT(ID) 
				 FROM {$this->wpdb->posts}
				 WHERE post_type = %s
				 AND ID NOT IN (
					 SELECT element_id FROM {$this->wpdb->prefix}icl_translations WHERE element_type = %s
				 )
			",
			array( 'attachment', 'post_attachment' )
		);
		$found     = (int) $this->wpdb->get_var( $count_sql );

		$attachments_prepared = $this->wpdb->prepare(
			"
			SELECT ID 
				 FROM {$this->wpdb->posts}
				 WHERE post_type = %s
				 AND ID NOT IN (
					 SELECT element_id FROM {$this->wpdb->prefix}icl_translations WHERE element_type = %s
				 )
				 LIMIT %d
			",
			array( 'attachment', 'post_attachment', $limit )
		);
		$attachments          = $this->wpdb->get_col( $attachments_prepared );

		foreach ( $attachments as $attachment_id ) {
			$this->sitepress->set_element_language_details( $attachment_id, 'post_attachment', false, $default_language );
		}
		$response['left'] = max( $found - $limit, 0 );
		if ( $response['left'] ) {
			// phpcs:ignore WordPress.WP.I18n.MissingTranslatorsComment
			$response['message'] = sprintf( __( 'Setting language to media. %d left', 'sitepress' ), $response['left'] );
		} else {
			$response['message'] = sprintf( __( 'Setting language to media: done!', 'sitepress' ), $response['left'] );
		}

		echo wp_json_encode( $response );
		exit;
	}

	public function ajax_save_should_handle_media_auto_setting() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_save_should_handle_media_auto_setting' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$isEnabled = (bool) $_POST['isEnabled'];
		Option::setShouldHandleMediaAuto( $isEnabled );

		if ( $isEnabled ) {
			$endpoint = make( \WPML\TM\Settings\ProcessExistingMediaInPosts::class );
			$this->background_task_service->add( $endpoint, wpml_collect( [] ) );
		} else {
			Option::setShouldShowHandleMediaAutoBannerAfterUpgrade();
			Option::setShouldShowHandleMediaAutoNotice30DaysAfterUpgrade();
		}

		wp_send_json( [] );
	}

	public function ajax_batch_scan_prepare() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_scan_prepare' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$this->batch_scan_prepare();
	}

	public function batch_scan_prepare( $outputResult = true ) {
		$response = array();
		$this->wpdb->delete( $this->wpdb->postmeta, array( 'meta_key' => 'wpml_media_processed' ) );

		$response['message'] = '';

		if ( $outputResult ) {
			wp_send_json( $response );
		}
	}

	public function ajax_batch_mark_processed() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_mark_processed' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$this->batch_mark_processed();
	}

	public function batch_mark_processed( $outputResult = true ) {

		$response                    = [];
		$wpmlMediaProcessedMetaValue = 1;
		$limit                       = 300;

		/**
		 * Query to get count of attachments from wp_posts table to decide how many rounds we should loop according to $limit
		 */
		$attachmentsCountQuery         = "SELECT COUNT(ID) from {$this->wpdb->posts} where post_type = %s";
		$attachmentsCountQueryPrepared = $this->wpdb->prepare( $attachmentsCountQuery, 'attachment' );

		/**
		 * Retrieving count of attachments
		 */
		$attachmentsCount = $this->wpdb->get_var( $attachmentsCountQueryPrepared );

		/**
		 * Query to get limited number of attachments with metadata up to $limit
		 *
		 * We join with the wp_postmeta table to also retrieve any related data of attachments in this table,
		 * we only need the related data when the wp_postmeta.metavalue is null or != 1 because if it equals 1 then it doesn't need to be processed again
		 */
		$limitedAttachmentsWithMetaDataQuery = "SELECT posts.ID, post_meta.post_id, post_meta.meta_key, post_meta.meta_value
		FROM {$this->wpdb->posts} AS posts
		LEFT JOIN {$this->wpdb->postmeta} AS post_meta
		ON posts.ID = post_meta.post_id AND post_meta.meta_key = %s
		WHERE posts.post_type = %s AND (post_meta.meta_value IS NULL OR post_meta.meta_value != %d)
		LIMIT %d";

		$limitedAttachmentsWithMetaDataQueryPrepared = $this->wpdb->prepare( $limitedAttachmentsWithMetaDataQuery,
			[
				self::WPML_MEDIA_PROCESSED_META_KEY,
				'attachment',
				1,
				$limit,
			] );


		/**
		 * Calculating loop rounds for processing attachments
		 */
		$attachmentsProcessingLoopRounds = $attachmentsCount ? ceil( $attachmentsCount / $limit ) : 0;

		/**
		 * Callback function used to decide if attachment already has metadata or not
		 *
		 * @param $attachmentWithMetaData
		 *
		 * @return bool
		 */
		$attachmentHasNoMetaData = function ( $attachmentWithMetaData ) {
			return Obj::prop( 'post_id', $attachmentWithMetaData ) === null &&
				Obj::prop( 'meta_key', $attachmentWithMetaData ) === null &&
				Obj::prop( 'meta_value', $attachmentWithMetaData ) === null;
		};

		/**
		 * Callback function that prepares values to be inserted in the wp_postmeta table
		 *
		 * @param $attachmentId
		 *
		 * @return array
		 */
		$prepareInsertAttachmentsMetaValues = function ( $attachmentId ) use ( $wpmlMediaProcessedMetaValue ) {
			// The order of returned items is important, it represents (meta_value, meta_key, post_id) when insert into wp_postmeta table is done
			return [ $wpmlMediaProcessedMetaValue, self::WPML_MEDIA_PROCESSED_META_KEY, $attachmentId ];
		};


		/**
		 * Looping through the retrieved limited number of attachments with metadata
		 */
		for ( $i = 0; $i < $attachmentsProcessingLoopRounds; $i ++ ) {

			/**
			 * Retrieving limited number of attachments with metadata
			 */
			$attachmentsWithMetaData = $this->wpdb->get_results( $limitedAttachmentsWithMetaDataQueryPrepared );

			if ( is_array( $attachmentsWithMetaData ) && count( $attachmentsWithMetaData ) ) {

				/**
				 * Filtering data to separate existing and non-existing attachments with metdata
				 */
				list( $notExistingMetaAttachmentIds, $existingAttachmentsWithMetaData ) = \WPML\FP\Lst::partition( $attachmentHasNoMetaData, $attachmentsWithMetaData );

				if ( is_array( $notExistingMetaAttachmentIds ) && count( $notExistingMetaAttachmentIds ) ) {

					/**
					 * If we have attachments with no related data in wp_postmeta table, we start inserting values for it in wp_postmeta
					 */

					// Getting only attachments Ids
					$notExistingAttachmentsIds = \WPML\FP\Lst::pluck( 'ID', $notExistingMetaAttachmentIds );

					// Preparing placeholders to be used in INSERT query
					/** @phpstan-ignore-next-line */
					$attachmentMetaValuesPlaceholders = implode( ',', \WPML\FP\Lst::repeat( '(%d, %s, %d)', count( $notExistingAttachmentsIds ) ) );

					// Preparing INSERT query
					$insertAttachmentsMetaQuery = "INSERT INTO {$this->wpdb->postmeta} (meta_value, meta_key, post_id) VALUES ";
					$insertAttachmentsMetaQuery .= $attachmentMetaValuesPlaceholders;

					// Preparing values to be inserted, at his point they're in separate arrays
					/** @phpstan-ignore-next-line */
					$insertAttachmentsMetaValues = array_map( $prepareInsertAttachmentsMetaValues, $notExistingAttachmentsIds );
					// Merging all values together in one array to be used wpdb->prepare function so each value is placed in a placeholder
					$insertAttachmentsMetaValues = array_merge( ...$insertAttachmentsMetaValues );

					// Start replacing placeholders with values and run query
					$insertAttachmentsMetaQuery = $this->wpdb->prepare( $insertAttachmentsMetaQuery, $insertAttachmentsMetaValues );
					$this->wpdb->query( $insertAttachmentsMetaQuery );
				}

				if ( count( $existingAttachmentsWithMetaData ) ) {

					/**
					 * If we have attachments with related data in wp_postmeta table, we start updating meta_value in wp_postmeta
					 */

					$existingAttachmentsIds = \WPML\FP\Lst::pluck( 'ID', $existingAttachmentsWithMetaData );

					$attachmentsIn = wpml_prepare_in( $existingAttachmentsIds, '%d' );

					$updateAttachmentsMetaQuery = $this->wpdb->prepare( "UPDATE {$this->wpdb->postmeta} SET meta_value = %d WHERE post_id IN ({$attachmentsIn})",
						[
							$wpmlMediaProcessedMetaValue,
						]
					);

					$this->wpdb->query( $updateAttachmentsMetaQuery );
				}
			} else {
				/**
				 * When there are no more attachments with metadata found we get out of the loop
				 */

				break;
			}

		}

		Option::setSetupFinished();

		$response['message'] = __( 'Done!', 'sitepress' );

		if ( $outputResult ) {
			wp_send_json( $response );
		}
	}

	public function create_duplicated_media( $attachment ) {
		static $parents_processed = array();

		if ( $attachment->post_parent && ! in_array( $attachment->post_parent, $parents_processed ) ) {

			// see if we have translations.
			$post_type_prepared = $this->wpdb->prepare( "SELECT post_type FROM {$this->wpdb->posts} WHERE ID = %d", array( $attachment->post_parent ) );
			$post_type          = $this->wpdb->get_var( $post_type_prepared );
			$trid_prepared      = $this->wpdb->prepare(
				"SELECT trid FROM {$this->wpdb->prefix}icl_translations WHERE element_id=%d AND element_type = %s",
				array(
					$attachment->post_parent,
					'post_' . $post_type,
				)
			);
			$trid               = $this->wpdb->get_var( $trid_prepared );
			if ( $trid ) {

				$attachments_prepared = $this->wpdb->prepare(
					"SELECT ID FROM {$this->wpdb->posts} WHERE post_type = %s AND post_parent = %d",
					array(
						'attachment',
						$attachment->post_parent,
					)
				);
				$attachments          = $this->wpdb->get_col( $attachments_prepared );

				$translations = $this->sitepress->get_element_translations( $trid, 'post_' . $post_type );
				foreach ( $translations as $translation ) {
					if ( $translation->element_id && $translation->element_id != $attachment->post_parent ) {

						$attachments_in_translation_prepared = $this->wpdb->prepare(
							"SELECT ID FROM {$this->wpdb->posts} WHERE post_type = %s AND post_parent = %d",
							array(
								'attachment',
								$translation->element_id,
							)
						);
						$attachments_in_translation          = $this->wpdb->get_col( $attachments_in_translation_prepared );
						if ( sizeof( $attachments_in_translation ) == 0 ) {
							// only duplicate attachments if there a none already.
							foreach ( $attachments as $attachment_id ) {
								// duplicate the attachment
								self::create_duplicate_attachment( $attachment_id, $translation->element_id, $translation->language_code );
							}
						}
					}
				}
			}

			$parents_processed[] = $attachment->post_parent;

		} else {
			// no parent - set to default language

			$target_language = $this->sitepress->get_default_language();

			// Getting the trid and language, just in case image translation already exists
			$trid = $this->sitepress->get_element_trid( $attachment->ID, 'post_attachment' );
			if ( $trid ) {
				$target_language = $this->sitepress->get_language_for_element( $attachment->ID, 'post_attachment' );
			}

			$this->sitepress->set_element_language_details( $attachment->ID, 'post_attachment', $trid, $target_language );

		}

		// Duplicate the post meta of the source element the translation
		$source_element_id = SitePress::get_original_element_id_by_trid( $trid );
		$post_type         = get_post_type( (int) $source_element_id );
		if ( $source_element_id && 'attachment' === $post_type ) {
			$this->update_attachment_metadata( $source_element_id );
		}

		update_post_meta( $attachment->ID, 'wpml_media_processed', 1 );
	}

	function set_content_defaults_prepare() {

		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_set_content_prepare' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$response = array( 'message' => __( 'Saving settings...', 'sitepress' ) );
		echo wp_json_encode( $response );
		exit;
	}

	public function wpml_media_set_content_defaults() {

		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_set_content_defaults' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		$this->set_content_defaults();

	}

	private function set_content_defaults() {

		$always_translate_media = $_POST['always_translate_media'];
		$duplicate_media        = $_POST['duplicate_media'];
		$duplicate_featured     = $_POST['duplicate_featured'];
		$translateMediaLibraryTexts     = \WPML\API\Sanitize::stringProp('translate_media_library_texts', $_POST);

		$content_defaults_option = [
			'always_translate_media' => $always_translate_media == 'true',
			'duplicate_media'        => $duplicate_media == 'true',
			'duplicate_featured'     => $duplicate_featured == 'true',
		];

		Option::setNewContentSettings( $content_defaults_option );

		$settings                         = get_option( '_wpml_media' );
		$settings['new_content_settings'] = $content_defaults_option;
		$settings['translate_media_library_texts'] = $translateMediaLibraryTexts === 'true';

		update_option( '_wpml_media', $settings );

		$response = [
			'result'  => true,
			'message' => __( 'Done', 'sitepress' ),
		];
		wp_send_json_success( $response );
	}

	/**
	 * @return bool
	 */
	private function is_mt_homepage_screen() {
		/* phpcs:ignore WordPress.Security.NonceVerification.Recommended */
		return isset( $_GET['page'] ) && 'wpml-media' === $_GET['page'];
	}

	/**
	 * @return bool
	 */
	private function should_show_admin_notice_for_elementor_on_mt_homepage() {
		return (
			$this->is_mt_homepage_screen() &&
			! Option::isAdminNoticeForElementorOnMtHomepageDismissed() &&
			is_admin() &&
			is_plugin_active( 'elementor/elementor.php' )
		);
	}

	public function maybe_render_admin_notices() {
		if ( ! defined( 'WPML_TM_FOLDER' ) ) {
			return;
		}

		if ( $this->should_show_admin_notice_for_elementor_on_mt_homepage() ) {
			wp_enqueue_style( 'otgs-notices' );
			$this->render_admin_notice_for_elementor_on_mt_homepage();
		}

		if ( Option::shouldHandleMediaAuto() ) {
			return;
		}

		$screen = get_current_screen();
		if ( ! is_admin() || ! $screen ) {
			return;
		}

		// Exclude on add or edit post pages.
		$excluded_bases = [
			'post',
		];

		if ( in_array( $screen->base, $excluded_bases, true ) ) {
			return;
		}

		if ( Option::shouldShowHandleMediaAutoBannerAfterUpgrade() ) {
			$this->render_admin_banner_about_automatic_media_detection();
		}

		if ( ! Option::shouldShowHandleMediaAutoBannerAfterUpgrade() && Option::shouldShowHandleMediaAutoNotice30DaysAfterUpgrade() ) {
			wp_enqueue_style( 'otgs-notices' );
			$this->render_admin_notice_about_automatic_media_detection();
		}
	}

	private function render_admin_banner_about_automatic_media_detection() {
		?>
		<section id="admin_banner_about_automatic_media_detection" class="wpml-banner show" aria-labelledby="wpml-banner-disabled-header">
			<h3>
				<?php echo esc_html__( 'New in WPML 4.8 - Automatic image and media detection', 'sitepress' ); ?>
				<button class="dismiss-button" aria-label="<?php echo esc_attr__( 'Close banner', 'sitepress' ); ?>"><span class="otgs-ico otgs-ico-cancel"></span></button>
			</h3>
			<p><?php echo esc_html__(
					'WPML can now automatically detect what types of texts (alt, caption, title) your images use. ' .
					'Enable this option to avoid duplicate fields in the translation editor and missing translations for your images.',
					'sitepress'
				); ?></p>
			<div class="wpml-banner-actions">
				<a href="<?php echo $this->get_media_settings_link(); ?>">
					<button class="wpml-button base-btn button-with-progress">
						<span class="button-text"><?php echo esc_html__( 'Enable it now', 'sitepress' ); ?></span>
					</button>
				</a>
				<a
					class="external-link"
					href="https://wpml.org/documentation/translating-your-contents/using-the-translation-editor/switching-from-classic-to-advanced-translation-editor/?utm_source=plugin&amp;utm_medium=gui&amp;utm_campaign=cte-banner"
					target="_blank"
					aria-label=""
				>
					<span>
						<?php echo esc_html__( 'Learn more about media translation', 'sitepress' ); ?>
					</span>
				</a>
			</div>
		</section>
		<?php
	}

	public function ajax_dismiss_should_handle_media_auto_banner() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_dismiss_should_handle_media_auto_banner' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		Option::removeShouldShowHandleMediaAutoBannerAfterUpgrade();

		wp_send_json( [] );
	}

	private function render_admin_notice_about_automatic_media_detection() {
		?>
		<div class="wpml-notices-list">
			<div id="admin_banner_about_automatic_media_detection_after_30_days" class="warning notice-warning otgs-notice wpml-notices-list-notice">
				<button class="dismiss-button dismiss-button-in-top-right" aria-label="<?php echo esc_attr__( 'Close banner', 'sitepress' ); ?>"><span class="otgs-ico otgs-ico-cancel"></span></button>
				<p><?php echo esc_html__( 'We strongly recommend enabling WPML\'s automatic detection for image texts to avoid duplicated media fields and missing translations.', 'sitepress' ); ?>
					<a href="https://wpml.org/documentation/translating-your-contents/using-the-translation-editor/switching-from-classic-to-advanced-translation-editor/?utm_source=plugin&amp;utm_medium=gui&amp;utm_campaign=cte-banner" class="external-link"><?php echo esc_html__( 'Learn more', 'sitepress' ); ?></a></p>
				<a href="<?php echo $this->get_media_settings_link(); ?>">
					<button class="wpml-button base-btn button-with-progress button-horizontal-padding">
						<span class="button-text"><?php echo esc_html__( 'Enable it now', 'sitepress' ); ?></span>
					</button>
				</a>
			</div>
		</div>
		<?php
	}

	public function ajax_dismiss_should_handle_media_auto_notice() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_dismiss_should_handle_media_auto_notice' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		Option::removeShouldShowHandleMediaAutoNotice30DaysAfterUpgrade();

		wp_send_json( [] );
	}

	private function render_admin_notice_for_elementor_on_mt_homepage() {
		?>
		<div class="wpml-notices-list">
			<div id="admin_banner_for_elementor_on_mt_homepage" class="warning notice-warning otgs-notice wpml-notices-list-notice">
				<button class="dismiss-button dismiss-button-in-top-right" aria-label="<?php echo esc_attr__( 'Close banner', 'sitepress' ); ?>"><span class="otgs-ico otgs-ico-cancel"></span></button>
				<p><?php echo esc_html__( 'As this site uses Elementor, changes you make here might not be visible on the front-end. In this case, go to Elementor settings and clear its cache.', 'sitepress' ); ?>
			</div>
		</div>
		<?php
	}

	public function ajax_dismiss_admin_notice_for_elementor_on_mt_homepage_notice() {
		$nonce = isset( $_POST['nonce'] ) ? sanitize_text_field( $_POST['nonce'] ) : '';

		if ( ! wp_verify_nonce( $nonce, 'wpml_media_dismiss_admin_notice_for_elementor_on_mt_homepage_notice' ) ) {
			wp_send_json_error( esc_html__( 'Invalid request!', 'sitepress' ) );
		}

		Option::setIsAdminNoticeForElementorOnMtHomepageDismissed();

		wp_send_json( [] );
	}

	private function get_media_settings_link() {
		return admin_url( 'admin.php?page=' . WPML_TM_FOLDER . WPML_Translation_Management::PAGE_SLUG_SETTINGS . '#' . WPML_Media_Settings::ID );
	}
}
