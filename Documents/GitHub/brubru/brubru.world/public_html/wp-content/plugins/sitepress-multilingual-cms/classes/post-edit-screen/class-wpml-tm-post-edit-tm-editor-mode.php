<?php

use WPML\API\Settings;
use WPML\Element\API\Translations;

class WPML_TM_Post_Edit_TM_Editor_Mode {

	const POST_META_KEY_USE_NATIVE        = '_wpml_post_translation_editor_native';
	const TM_KEY_FOR_POST_TYPE_USE_NATIVE = 'post_translation_editor_native_for_post_type';
	const TM_KEY_GLOBAL_USE_NATIVE        = 'post_translation_editor_native';

	const POST_META_KEY_USE_WPML        = '_wpml_post_translation_editor_wpml';
	const TM_KEY_FOR_POST_TYPE_USE_WPML = 'post_translation_editor_wpml_for_post_type';
	const TM_KEY_GLOBAL_USE_WPML        = 'post_translation_editor_wpml';

	/**
	 * Check post meta first
	 * Then check setting for post type
	 * Then finally check global setting
	 *
	 * @param mixed $deprecated (Deprecated) There is no need to pass `SitePress` instance.
	 * @param int $post_id
	 * @param bool $should_find_original_id (Optional) If not passing original ID, it will be found. Default: true
	 *
	 * @return bool
	 */
	public static function is_using_tm_editor( $deprecated, $post_id, $should_find_original_id = true ) {
		if ( $should_find_original_id ) {
			$original_id = (int) Translations::getOriginalId( $post_id, 'post_' . get_post_type( $post_id ) );
			$post_id = $original_id ?: $post_id;
		}

		$post_meta = get_post_meta( $post_id, self::POST_META_KEY_USE_NATIVE, true );
		if ( 'no' === $post_meta ) {
			return true;
		} elseif ( 'yes' === $post_meta ) {
			return false;
		}

		$tm_settings = self::init_settings();

		$post_type = get_post_type( $post_id );
		if ( isset( $tm_settings[ self::TM_KEY_FOR_POST_TYPE_USE_NATIVE ][ $post_type ] ) ) {
			return ! $tm_settings[ self::TM_KEY_FOR_POST_TYPE_USE_NATIVE ][ $post_type ];
		} else if ( isset( $tm_settings[ self::TM_KEY_FOR_POST_TYPE_USE_WPML ][ $post_type ] ) ) {
			return $tm_settings[ self::TM_KEY_FOR_POST_TYPE_USE_WPML ][ $post_type ];
		}

		return ! $tm_settings[ self::TM_KEY_GLOBAL_USE_NATIVE ];
	}

	/**
	 * @param string $post_type (Optional) Provide post type to check against it or empty for global setting.
	 *
	 * @return bool
	 */
	public static function is_post_type_using_wp_editor( $post_type = '' ) : bool {
		$tm_settings = self::init_settings();

		if ( $post_type && isset( $tm_settings[ self::TM_KEY_FOR_POST_TYPE_USE_NATIVE ][ $post_type ] ) ) {
			return (bool) $tm_settings[ self::TM_KEY_FOR_POST_TYPE_USE_NATIVE ][ $post_type ];
		}

		return (bool) $tm_settings[ self::TM_KEY_GLOBAL_USE_NATIVE ] ?? false;
	}

	/**
	 * @param mixed $deprecated (Deprecated) There is no need to pass `SitePress` instance.
	 * @param int $postId
	 *
	 * @return array
	 */
	public static function get_editor_settings( $deprecated, $postId ) {
		$useTmEditor = \WPML_TM_Post_Edit_TM_Editor_Mode::is_using_tm_editor( null, $postId );
		$useTmEditor = apply_filters( 'wpml_use_tm_editor', $useTmEditor, $postId );

		$result = self::get_blocked_posts( [ $postId ] );

		if ( isset($result[$postId]) ) {
			$isWpmlEditorBlocked = true;
			$reason              = $result[$postId];
		} else {
			$isWpmlEditorBlocked = false;
			$reason              = '';
		}

		return [
			$useTmEditor,
			$isWpmlEditorBlocked,
			$reason,
		];
	}

	/**
	 * @param array $postIds list of post ids that should be checked is blocked.
	 *
	 * @return array list of post ids that are blocked and the reason why they are blocked.
	 */
	public static function get_blocked_posts( $postIds ) {
		/**
		 * Returns the editor settings for the posts - is the WPML editor blocked, and if so, why.
		 *
		 * Filter returns an array of: the reason why its blocked indexed by the post ID.
		 *
		 * @since 4.6.0
		 *
		 * @param array $defaultParams The default parameters that should be returned
		 * @param array $postIds An array of post IDs
		 */
		return apply_filters( 'wpml_tm_editor_exclude_posts', [], $postIds );
	}

	/**
	 * @return array
	 */
	private static function init_settings() {
		$tm_settings = Settings::get( 'translation-management', [] );

		/**
		 * Until a user explicitly change the settings through
		 * the switcher ( @see WPML_TM_Post_Edit_TM_Editor_Select::save_mode ),
		 * we'll set it by default at run time:
		 * - Native editor set to true if using the manual method
		 * - Native editor set to false otherwise
		 */
		if ( ! isset( $tm_settings['post_translation_editor_native'] ) ) {
			if ( ( (string) ICL_TM_TMETHOD_MANUAL === (string) $tm_settings['doc_translation_method'] ) ) {
				$tm_settings['post_translation_editor_native'] = true;
			} else {
				$tm_settings['post_translation_editor_native'] = false;
			}

			if ( ! isset( $tm_settings['post_translation_editor_native_for_post_type'] ) ) {
				$tm_settings['post_translation_editor_native_for_post_type'] = [];
			}
		}

		return $tm_settings;
	}

	/**
	 * @param null|string $post_type
	 */
	public static function delete_all_posts_option( $post_type = null ) {
		global $wpdb;

		if ( $post_type ) {
			$meta_keys  = [ self::POST_META_KEY_USE_NATIVE, self::POST_META_KEY_USE_WPML ];
			$prepare_in = wpml_prepare_in( $meta_keys );

			$wpdb->query(
				$wpdb->prepare(
					"DELETE postmeta FROM {$wpdb->postmeta} AS postmeta
					 INNER JOIN {$wpdb->posts} AS posts ON posts.ID = postmeta.post_id
					 WHERE posts.post_type = %s AND postmeta.meta_key IN ( $prepare_in )",
					$post_type
				)
			);
		} else {
			delete_post_meta_by_key( self::POST_META_KEY_USE_NATIVE );
			delete_post_meta_by_key( self::POST_META_KEY_USE_WPML );
		}
	}
}
