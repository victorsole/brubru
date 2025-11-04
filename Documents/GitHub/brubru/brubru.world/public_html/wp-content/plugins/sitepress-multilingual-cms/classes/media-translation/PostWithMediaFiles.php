<?php

namespace WPML\MediaTranslation;

use WPML\FP\Fns;
use WPML\LIB\WP\Post;
use WPML_Post_Element;

class PostWithMediaFiles {
	const POSTS_QUEUE_WITH_DUPLICATED_COPIED_MEDIA_SETTING = 'posts_queue_with_duplicated_copied_media';

	const COPIED_MEDIA_IDS_SETTING = 'copied_media_ids';

	const REFERENCED_MEDIA_IDS_SETTING = 'referenced_media_ids';

	/**
	 * @var int
	 */
	private $post_id;
	/**
	 * @var MediaImgParse
	 */
	private $media_parser;
	/**
	 * @var MediaAttachmentByUrlFactory
	 */
	private $attachment_by_url_factory;
	/**
	 * @var \SitePress $sitepress
	 */
	private $sitepress;
	/**
	 * @var \WPML_Custom_Field_Setting_Factory
	 */
	private $cf_settings_factory;
	/**
	 * @var CopiedAndReferencedMediaExtractor
	 */
	private $copied_and_referenced_media_extractor;
	/**
	 * @var UsageOfMediaFilesInPosts
	 */
	private $usage_of_media_files_in_posts;

	/**
	 * WPML_Media_Post_With_Media_Files constructor.
	 *
	 * @param $post_id
	 * @param MediaImgParse $media_parser
	 * @param MediaAttachmentByUrlFactory $attachment_by_url_factory
	 * @param \SitePress $sitepress
	 * @param \WPML_Custom_Field_Setting_Factory $cf_settings_factory
	 * @param CopiedAndReferencedMediaExtractor $copied_and_referenced_media_extractor
	 * @param UsageOfMediaFilesInPosts $usage_of_media_files_in_posts
	 */
	public function __construct(
		$post_id,
		MediaImgParse $media_parser,
		MediaAttachmentByUrlFactory $attachment_by_url_factory,
		\SitePress $sitepress,
		\WPML_Custom_Field_Setting_Factory $cf_settings_factory,
		CopiedAndReferencedMediaExtractor $copied_and_referenced_media_extractor,
		UsageOfMediaFilesInPosts $usage_of_media_files_in_posts
	) {
		$this->post_id                               = $post_id;
		$this->media_parser                          = $media_parser;
		$this->attachment_by_url_factory             = $attachment_by_url_factory;
		$this->sitepress                             = $sitepress;
		$this->cf_settings_factory                   = $cf_settings_factory;
		$this->copied_and_referenced_media_extractor = $copied_and_referenced_media_extractor;
		$this->usage_of_media_files_in_posts         = $usage_of_media_files_in_posts;
	}

	/**
	 * @return array
	 */
	public function get_copied_media_ids() {
		$ids = get_post_meta( $this->post_id, self::COPIED_MEDIA_IDS_SETTING, true );
		return is_array( $ids ) ? $ids : [];
	}

	/**
	 * @return array
	 */
	public function get_referenced_media_ids() {
		$ids = get_post_meta( $this->post_id, self::REFERENCED_MEDIA_IDS_SETTING, true );
		return is_array( $ids ) ? $ids : [];
	}

	public function get_copied_and_referenced__media_ids() {
		return array_merge(
			$this->get_copied_media_ids(),
			$this->get_referenced_media_ids()
		);
	}

	public function save_to_posts_queue_with_duplicated_copied_media() {
		$copied_media_ids = $this->get_copied_media_ids();

		if ( count( $copied_media_ids ) === 0 ) {
			return;
		}

		$filtered_copied_media_ids = [];
		foreach ( $copied_media_ids as $copied_media_id ) {
			$usages_as_reference_in_posts = $this->usage_of_media_files_in_posts->getUsagesAsReference( $copied_media_id );
			if ( count( $usages_as_reference_in_posts ) > 0 ) {
				continue;
			}
			$filtered_copied_media_ids[] = $copied_media_id;
		}
		$copied_media_ids = $filtered_copied_media_ids;

		if ( count( $copied_media_ids ) === 0 ) {
			return;
		}

		$queue = $this->sitepress->get_setting( self::POSTS_QUEUE_WITH_DUPLICATED_COPIED_MEDIA_SETTING, [] );
		if ( in_array( $this->post_id, $queue ) ) {
			return;
		}

		$queue[] = $this->post_id;
		$this->sitepress->set_setting( self::POSTS_QUEUE_WITH_DUPLICATED_COPIED_MEDIA_SETTING, $queue );
		$this->sitepress->save_settings();
	}

	public function clear_posts_queue_with_duplicated_copied_media() {
		$this->sitepress->set_setting( self::POSTS_QUEUE_WITH_DUPLICATED_COPIED_MEDIA_SETTING, [] );
		$this->sitepress->save_settings();
	}

	public function delete_duplicated_copied_media() {
		$default_language_code = $this->sitepress->get_default_language();
		$copied_media_ids      = get_post_meta( $this->post_id, self::COPIED_MEDIA_IDS_SETTING, true );

		foreach ( $copied_media_ids as $copied_media_id ) {
			$trid = $this->sitepress->get_element_trid( $copied_media_id, 'post_attachment' );
			if ( ! $trid ) {
				continue;
			}

			$texts = $this->get_image_texts( $copied_media_id );

			$translations = $this->sitepress->get_element_translations( $trid, 'post_attachment', true, true );
			foreach ( $translations as $translation ) {
				if ( $translation->language_code === $default_language_code || (int) $translation->element_id === (int) $copied_media_id ) {
					continue;
				}

				$translation_texts = $this->get_image_texts( $translation->element_id );
				if (
					$texts['caption'] !== $translation_texts['caption'] ||
					$texts['description'] !== $translation_texts['description'] ||
					$texts['alt'] !== $translation_texts['alt']
				) {
					continue;
				}

				$this->delete_duplicated_attachment( $translation->element_id );
			}
		}
	}

	private function get_image_texts( $attachment_id ) {
		$texts = [
			'caption'     => '',
			'description' => '',
			'alt'         => '',
		];

		$attachment = get_post( $attachment_id );
		if ( ! $attachment ) {
			return $texts;
		}

		if ( $attachment->post_excerpt ) {
			$texts['caption'] = $attachment->post_excerpt;
		}
		if ( $attachment->post_content ) {
			$texts['description'] = $attachment->post_content;
		}
		if ( $alt = get_post_meta( $attachment_id, '_wp_attachment_image_alt', true ) ) {
			$texts['alt'] = $alt;
		}

		return $texts;
	}

	/**
	 * We should not call wp_delete_attachment here because it can trigger hooks with original attachment filepath.
	 */
	private function delete_duplicated_attachment( $post_id ) {
		global $wpdb;

		$post = $wpdb->get_row( $wpdb->prepare( "SELECT * FROM $wpdb->posts WHERE ID = %d", $post_id ) );

		if ( ! $post ) {
			return $post;
		}

		$post = get_post( $post );

		if ( 'attachment' !== $post->post_type ) {
			return false;
		}

		delete_post_meta( $post_id, '_wp_trash_meta_status' );
		delete_post_meta( $post_id, '_wp_trash_meta_time' );

		wp_delete_object_term_relationships( $post_id, array( 'category', 'post_tag' ) );
		wp_delete_object_term_relationships( $post_id, get_object_taxonomies( $post->post_type ) );

		delete_metadata( 'post', 0, '_thumbnail_id', $post_id, true );

		$post_meta_ids = $wpdb->get_col( $wpdb->prepare( "SELECT meta_id FROM $wpdb->postmeta WHERE post_id = %d ", $post_id ) );
		foreach ( $post_meta_ids as $mid ) {
			delete_metadata_by_mid( 'post', $mid );
		}

		do_action( 'delete_post', $post_id, $post );
		$result = $wpdb->delete( $wpdb->posts, array( 'ID' => $post_id ) );
		if ( ! $result ) {
			return false;
		}
		do_action( 'deleted_post', $post_id, $post );

		clean_post_cache( $post );

		return $post;
	}

	public function get_usages_of_media_file_in_posts( $media_file_id ) {
		return [
			$this->usage_of_media_files_in_posts->getUsagesAsCopy( $media_file_id ),
			$this->usage_of_media_files_in_posts->getUsagesAsReference( $media_file_id ),
		];
	}

	public function extract_and_save_media_ids() {
		$post_media_data = $this->get_media_data_from_post_content_and_meta();
		list(
			$copied_media_file_ids,
			$referenced_media_file_ids
			) = self::extract_media_ids( $post_media_data );
		$this->update_usages_of_media_files_in_posts(
			$copied_media_file_ids,
			$referenced_media_file_ids
		);

		update_post_meta( $this->post_id, self::COPIED_MEDIA_IDS_SETTING, $copied_media_file_ids );
		update_post_meta( $this->post_id, self::REFERENCED_MEDIA_IDS_SETTING, $referenced_media_file_ids );
	}

	public static function extract_media_ids( $post_media_data ) {
		$copied_media_file_ids     = [];
		$referenced_media_file_ids = [];

		if ( is_array( $post_media_data ) && isset( $post_media_data[0] ) && isset( $post_media_data[1] ) ) {
			$copied_media_file_ids     = is_array( $post_media_data[0] ) ? self::extract_attachment_ids( $post_media_data[0] ) : [];
			$referenced_media_file_ids = is_array( $post_media_data[1] ) ? self::extract_attachment_ids( $post_media_data[1] ) : [];
		}

		return [
			$copied_media_file_ids,
			$referenced_media_file_ids,
		];
	}

	private function update_usages_of_media_files_in_posts( $copied_media_file_ids, $referenced_media_file_ids ) {
		return $this->usage_of_media_files_in_posts->updateUsages(
			$this->post_id,
			$this->get_copied_media_ids(),
			$this->get_referenced_media_ids(),
			$copied_media_file_ids,
			$referenced_media_file_ids
		);
	}

	public function remove_usage_of_media_files_in_post() {
		$this->usage_of_media_files_in_posts->updateUsages(
			$this->post_id,
			$this->get_copied_media_ids(),
			$this->get_referenced_media_ids(),
			[],
			[]
		);
	}

	/**
	 * @param array $post_media_data
	 *
	 * @return array
	 */
	private static function extract_attachment_ids( $post_media_data ) {
		$media_file_ids = [];
		foreach ( $post_media_data as $media_data ) {
			if ( in_array( $media_data['attachment_id'], $media_file_ids ) || is_null( $media_data['attachment_id'] ) ) {
				continue;
			}

			$media_file_ids[] = $media_data['attachment_id'];
		}

		return $media_file_ids;
	}

	/**
	 * @param bool $get_attachment_ids_from_urls
	 */
	public function get_media_data_from_post_content_and_meta( $get_attachment_ids_from_urls = true ) {
		$post = get_post( $this->post_id );
		if ( ! $post ) {
			return [ [], [] ];
		}

		list( $copied_media_ids, $referenced_media_ids ) = $this->copied_and_referenced_media_extractor->extract( $post, $get_attachment_ids_from_urls );

		$media_localization_settings = MediaSettings::get_setting( 'media_files_localization' );
		if ( $media_localization_settings['custom_fields'] ) {
			$custom_fields_content = $this->get_content_in_translatable_custom_fields();
			$custom_fields_media   = $this->media_parser->get_imgs( $custom_fields_content );
			$custom_media_ids      = $this->_get_ids_from_media_array( $custom_fields_media );
			foreach ( $custom_media_ids as $custom_media_id ) {
				$referenced_media_ids[] = [
					'attributes'    => [
						'src'     => null,
						'alt'     => '',
						'caption' => '',
					],
					'attachment_id' => $custom_media_id,
				];
			}
		}

		if ( $gallery_media_ids = $this->get_gallery_media_ids( $post->post_content ) ) {
			foreach ( $gallery_media_ids as $gallery_media_id ) {
				$referenced_media_ids[] = [
					'attributes'    => [
						'src'     => null,
						'alt'     => '',
						'caption' => '',
					],
					'attachment_id' => $gallery_media_id,
				];
			}
		}

		return [ $copied_media_ids, $referenced_media_ids ];
	}

	public function get_media_ids() {
		$media_ids = [];

		if ( $post = get_post( $this->post_id ) ) {

			$content_to_parse   = apply_filters( 'wpml_media_content_for_media_usage', $post->post_content, $post );
			$post_content_media = $this->media_parser->get_imgs( $content_to_parse );
			$media_ids          = $this->_get_ids_from_media_array( $post_content_media );

			if ( $featured_image = get_post_meta( $this->post_id, '_thumbnail_id', true ) ) {
				$media_ids[] = $featured_image;
			}

			$media_localization_settings = MediaSettings::get_setting( 'media_files_localization' );
			if ( $media_localization_settings['custom_fields'] ) {
				$custom_fields_content = $this->get_content_in_translatable_custom_fields();
				$custom_fields_media   = $this->media_parser->get_imgs( $custom_fields_content );
				$media_ids             = array_merge( $media_ids, $this->_get_ids_from_media_array( $custom_fields_media ) );
			}

			if ( $gallery_media_ids = $this->get_gallery_media_ids( $content_to_parse ) ) {
				$media_ids = array_unique( array_values( array_merge( $media_ids, $gallery_media_ids ) ) );
			}

			if ( $attached_media_ids = $this->get_attached_media_ids( $this->post_id ) ) {
				$media_ids = array_unique( array_values( array_merge( $media_ids, $attached_media_ids ) ) );
			}

			$post_media_data = $this->copied_and_referenced_media_extractor->extract( $post );

			if ( is_array( $post_media_data ) && isset( $post_media_data[1] ) ) {
				$referenced_media_file_ids = is_array( $post_media_data[1] ) ? self::extract_attachment_ids( $post_media_data[1] ) : [];
				$media_ids = array_merge(
					$media_ids,
					$referenced_media_file_ids
				);
			}
		}

		return Fns::filter( Post::get(), apply_filters( 'wpml_ids_of_media_used_in_post', $media_ids, $this->post_id ) );
	}

	/**
	 * @param array $media_array
	 *
	 * @return array
	 */
	private function _get_ids_from_media_array( $media_array ) {
		$media_ids = [];
		foreach ( $media_array as $media ) {
			if ( isset( $media['attachment_id'] ) ) {
				$media_ids[] = $media['attachment_id'];
			} else {
				$attachment_by_url = $this->attachment_by_url_factory->create( $media['attributes']['src'], wpml_get_current_language() );
				if ( $attachment_id = $attachment_by_url->get_id() ) {
					$media_ids[] = $attachment_id;
				}

			}
		}

		return $media_ids;
	}

	/**
	 * @param string $post_content
	 *
	 * @return array
	 */
	private function get_gallery_media_ids( $post_content ) {

		$galleries_media_ids     = [];
		$gallery_shortcode_regex = '/\[gallery [^[]*ids=["\']([0-9,\s]+)["\'][^[]*\]/m';
		if ( preg_match_all( $gallery_shortcode_regex, $post_content, $matches ) ) {
			foreach ( $matches[1] as $gallery_ids_string ) {
				$media_ids_array = explode( ',', $gallery_ids_string );
				$media_ids_array = Fns::map( Fns::unary( 'intval' ), $media_ids_array );

				foreach ( $media_ids_array as $media_id ) {
					if ( 'attachment' === get_post_type( $media_id ) ) {
						$galleries_media_ids[] = $media_id;
					}

				}
			}
		}

		return $galleries_media_ids;
	}

	/**
	 * @param $languages
	 *
	 * @return array
	 */
	public function get_untranslated_media( $languages ) {

		$untranslated_media = [];

		$post_media = $this->get_media_ids();

		foreach ( $post_media as $attachment_id ) {

			$post_element = new WPML_Post_Element( $attachment_id, $this->sitepress );

			foreach ( $languages as $language ) {
				$translation = $post_element->get_translation( $language );
				if ( null === $translation || ! $this->media_file_is_translated( $attachment_id, $translation->get_id() ) ) {
					$untranslated_media[] = $attachment_id;
					break;
				}
			}

		}

		return $untranslated_media;
	}

	private function media_file_is_translated( $attachment_id, $translated_attachment_id ) {
		return get_post_meta( $attachment_id, '_wp_attached_file', true )
		       !== get_post_meta( $translated_attachment_id, '_wp_attached_file', true );
	}

	private function get_content_in_translatable_custom_fields() {
		$content = '';

		$post_meta = get_metadata( 'post', $this->post_id );

		if ( is_array( $post_meta ) ) {
			foreach ( $post_meta as $meta_key => $meta_value ) {
				$setting         = $this->cf_settings_factory->post_meta_setting( $meta_key );
				$is_translatable = $this->sitepress->get_wp_api()
				                                   ->constant( 'WPML_TRANSLATE_CUSTOM_FIELD' ) === $setting->status();
				if ( is_string( $meta_value[0] ) && $is_translatable ) {
					$content .= $meta_value[0];
				}
			}
		}

		return $content;
	}

	private function get_attached_media_ids( $post_id ) {
		$attachments = get_children(
			[
				'post_parent' => $post_id,
				'post_status' => 'inherit',
				'post_type'   => 'attachment',
			]
		);

		return array_keys( $attachments );
	}
}
