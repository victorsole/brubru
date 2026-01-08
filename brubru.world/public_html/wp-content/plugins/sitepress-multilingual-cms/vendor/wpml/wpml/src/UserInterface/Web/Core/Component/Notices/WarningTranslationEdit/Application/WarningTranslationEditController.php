<?php

namespace WPML\UserInterface\Web\Core\Component\Notices\WarningTranslationEdit\Application;

use WPML\Core\Port\Event\EventListenerInterface;
use WPML\UserInterface\Web\Core\Port\Asset\AssetInterface;
use WPML\UserInterface\Web\Core\SharedKernel\Config\Script;
use WPML\UserInterface\Web\Core\SharedKernel\Config\Style;

class WarningTranslationEditController implements EventListenerInterface {
  const SCRIPT_HANDLE = 'wpml_warning_translation_edit';

  /** @var TranslationEditorInterface */
  private $translationEditor;

  /** @var AssetInterface $asset */
  private $asset;


  public function __construct(
    TranslationEditorInterface $translationEditor,
    AssetInterface $asset
  ) {
    $this->translationEditor = $translationEditor;
    $this->asset = $asset;
  }


  /**
   * @param int           $postId
   * @param string        $pageBuilderName
   * @param array<string> $args
   *
   * @return void
   */
  public function maybeShowPageBuilderWarning( $postId, $pageBuilderName, $args = [] ) {
    $defaultArgs = [
      'iframeModeQuerySelector' => ''
    ];

    $args = array_merge( $defaultArgs, $args );

    $translationEditorUrl = $this->translationEditor->getTranslationEditorLink( $postId );
    if ( $translationEditorUrl ) {
        /** @phpstan-ignore-next-line */
        $this->enqueueAssets( $pageBuilderName, $translationEditorUrl, $args );
    }
  }


  /**
   * @param string $pageBuilderName
   * @param string $translationEditorUrl
   * @param array{iframeModeQuerySelector: string} $args $args
   * @return void
   */
  private function enqueueAssets( $pageBuilderName, $translationEditorUrl, $args ) {
    $script_m = new Script( 'wpml-modules' );
    $script_m->setSrc( 'public/js/node-modules.js' );
    $this->asset->enqueueScript( $script_m );

    $script = new Script( self::SCRIPT_HANDLE );
    $script->setSrc( 'public/js/notice-warning-translation-edit.js' )
        ->setScriptData(
          [
              'page_builder_name' => $pageBuilderName,
              'translation_editor_url' => $translationEditorUrl,
              'iframe_mode_query_selector' => $args['iframeModeQuerySelector']
          ]
        )
        ->setScriptVarName( self::SCRIPT_HANDLE )
        ->setDependencies( ['wpml-modules', 'wp-i18n'] );

    $style = new Style( self::SCRIPT_HANDLE.'_css' );
    $style->setSrc( 'public/css/notice-warning-translation-edit.css' );

    $this->asset->enqueueScript( $script );
    $this->asset->enqueueStyle( $style );
  }


}
