<?php

namespace WPML\TM\PostEditScreen;

use Hamcrest\Core\Set;
use WPML\Element\API\PostTranslations;
use WPML\Element\API\Translations;
use WPML\FP\Fns;
use WPML\LIB\WP\Hooks;
use WPML\TM\PostEditScreen\Endpoints\SetEditorMode;
use WPML\Core\WP\App\Resources;
use WPML\API\Settings;
use function WPML\FP\spreadArgs;

class TranslationEditorPostSettings {
	private $sitepress;

	public function __construct( $sitepress ) {
		$this->sitepress = $sitepress;
	}

	public function add_hooks() {
		Hooks::onAction( 'admin_enqueue_scripts' )
		     ->then( [ $this, 'localize' ] )
		     ->then( Resources::enqueueApp( 'postEditTranslationEditor' ) );

		$render = Fns::once( spreadArgs( [ $this, 'render' ] ) );

		Hooks::onAction( 'wpml_before_post_edit_translations_table' )
		     ->then( $render );

		Hooks::onAction( 'wpml_before_post_edit_translations_summary' )
		     ->then( $render );
	}

	public static function localize() {
		return [
			'name' => 'wpml_translation_post_editor',
			'data' => [
				'endpoints' => [
					'setEditorMode' => SetEditorMode::class,
				],
				'urls' => [
					'tmdashboard' => admin_url( 'admin.php?page=tm%2Fmenu%2Fmain.php' ),
				]
			],
		];
	}

	public function render( $post ) {
		global $wp_post_types;

		if ( ! Translations::isOriginal( $post->ID, PostTranslations::get( $post->ID ) ) ) {
			return;
		}

		list( $useTmEditor, $isWpmlEditorBlocked, $reason ) = \WPML_TM_Post_Edit_TM_Editor_Mode::get_editor_settings( $this->sitepress, $post->ID );

		$editorModeFor = '';
		$tmSettings = $this->sitepress->get_setting( 'translation-management' );
		if ( $useTmEditor && ! $isWpmlEditorBlocked ) {
			list ( $enabledEditor, $editorModeFor ) = $this->getWpmlEditor( $post->ID, $tmSettings );
		} else {
			$enabledEditor = SetEditorMode::TRANSLATION_EDITOR_NATIVE;
		}
		$postTypeLabels = $wp_post_types[ $post->post_type ]->labels;
		$currentWpmlEditor     = (string) Settings::pathOr( ICL_TM_TMETHOD_ATE, [
			'translation-management',
			'doc_translation_method'
		] );

		$wpmlEditorName = ICL_TM_TMETHOD_ATE === $currentWpmlEditor
			? esc_attr__( 'Advanced Translation Editor', 'sitepress' )
			: esc_attr__( 'Classic Translation Editor', 'sitepress' );

		echo '<div id="translation-editor-post-settings" data-wpml-editor-name="' . $wpmlEditorName . '" data-post-id="' . $post->ID . '" data-post-type="' . $post->post_type . '" data-enabled-editor="' . $enabledEditor . '" data-wpml-editor-mode-for="' . $editorModeFor . '" data-is-wpml-blocked="' . $isWpmlEditorBlocked . '" data-wpml-blocked-reason="' . $reason . '" data-type-singular="' . $postTypeLabels->singular_name . '" data-type-plural="' . $postTypeLabels->name . '"></div>';
		echo '<div id="icl-translation-dashboard"></div>';
	}

	private function getWpmlEditor( $post_id, $tmSettings ) {
		// Check post meta first.
		$post_meta = get_post_meta( $post_id, \WPML_TM_Post_Edit_TM_Editor_Mode::POST_META_KEY_USE_WPML, true );
		if ( $post_meta ) {
			return [
				$post_meta,
				SetEditorMode::MODE_FOR_THIS_POST
			];
		}

		// Then check setting for post type.
		$post_type = get_post_type( $post_id );
		if ( isset( $tmSettings[ \WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_WPML ][ $post_type ] ) ) {
			return [
				$tmSettings[ \WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_FOR_POST_TYPE_USE_WPML ][ $post_type ],
				SetEditorMode::MODE_FOR_POST_TYPE
			];
		}

		// Last check global setting.
		if ( isset( $tmSettings[ \WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_GLOBAL_USE_WPML ] ) ) {
			return [
				$tmSettings[\WPML_TM_Post_Edit_TM_Editor_Mode::TM_KEY_GLOBAL_USE_WPML],
				SetEditorMode::MODE_FOR_GLOBAL
			];
		}

		// Use "dashboard" editor by default.
		return [
			SetEditorMode::TRANSLATION_EDITOR_DASHBOARD,
			SetEditorMode::MODE_FOR_GLOBAL
		];
	}
}
