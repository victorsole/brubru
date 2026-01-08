<?php

namespace WPML\TM\PostEditScreen\Endpoints;

use WPML\Ajax\IHandler;
use WPML\Collect\Support\Collection;
use WPML\FP\Right;
use WPML_TM_Post_Edit_TM_Editor_Mode;

class SetEditorMode implements IHandler {

	const TRANSLATION_EDITOR_DASHBOARD = 'dashboard';
	const TRANSLATION_EDITOR_WPML      = 'wpml';
	const TRANSLATION_EDITOR_NATIVE    = 'native';

	const MODE_FOR_GLOBAL    = 'global';
	const MODE_FOR_POST_TYPE = 'all_posts_of_type';
	const MODE_FOR_THIS_POST = 'this_post';

	/** @var \SitePress $sitepress */
	private $sitepress;

	public function __construct( \SitePress $sitepress ) {
		$this->sitepress = $sitepress;
	}

	public function run( Collection $data ) {
		$tmSettings = $this->sitepress->get_setting( 'translation-management' );

		$useNativeEditor = $data->get( 'enabledEditor' ) === self::TRANSLATION_EDITOR_NATIVE;
		$enabledEditor   = $data->get( 'enabledEditor' );
		$useWpmlEditor   = $enabledEditor === self::TRANSLATION_EDITOR_WPML
			|| $enabledEditor === self::TRANSLATION_EDITOR_DASHBOARD;
		$postId          = $data->get( 'postId' );
		$editorModeFor   = $data->get( 'editorModeFor' );

		$isSwitchingWpmlNative = $data->get( 'isSwitchingWpmlNative' );

		switch ( $editorModeFor ) {
			case self::MODE_FOR_GLOBAL:
				if ( $useNativeEditor ) {
					$tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_GLOBAL_USE_NATIVE ] = $useNativeEditor;
				} else {
					unset( $tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_GLOBAL_USE_NATIVE ] );
				}

				if ( $useWpmlEditor ) {
					$tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_GLOBAL_USE_WPML ] = $enabledEditor;
				} else {
					unset( $tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_GLOBAL_USE_WPML ] );
				}

				// If we are switching from WPML <-> native, we need to remove all posts option: post meta and post type settings.
				if ( $isSwitchingWpmlNative ) {
					unset( $tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_NATIVE ] );
					unset( $tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_WPML ] );

					WPML_TM_Post_Edit_TM_Editor_Mode::delete_all_posts_option();
				}

				$this->sitepress->set_setting( 'translation-management', $tmSettings, true );
				break;

			case self::MODE_FOR_POST_TYPE:
				$post_type = get_post_type( $postId );

				if ( $post_type ) {
					if ( $useNativeEditor ) {
						$tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_NATIVE ][ $post_type ] = $useNativeEditor;
					} else {
						unset( $tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_NATIVE ][ $post_type ] );
					}

					if ( $useWpmlEditor ) {
						$tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_WPML ][ $post_type ] = $enabledEditor;
					} else {
						unset( $tmSettings[ WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_WPML ][ $post_type ] );
					}

					// If we are switching from WPML <-> native, we need to remove all post meta.
					if ( $isSwitchingWpmlNative ) {
						WPML_TM_Post_Edit_TM_Editor_Mode::delete_all_posts_option( $post_type );
					}

					$this->sitepress->set_setting( 'translation-management', $tmSettings, true );
				}
				break;

			case self::MODE_FOR_THIS_POST:
				update_post_meta(
					$postId,
					WPML_TM_Post_Edit_TM_Editor_Mode::POST_META_KEY_USE_NATIVE,
					$useNativeEditor ? 'yes' : 'no'
				);

				if ( $useWpmlEditor ) {
					update_post_meta(
						$postId,
						WPML_TM_Post_Edit_TM_Editor_Mode::POST_META_KEY_USE_WPML,
						$enabledEditor
					);
				} else {
					delete_post_meta( $postId, WPML_TM_Post_Edit_TM_Editor_Mode::POST_META_KEY_USE_WPML );
				}
				break;
		}

		return Right::of( true );
	}
}
