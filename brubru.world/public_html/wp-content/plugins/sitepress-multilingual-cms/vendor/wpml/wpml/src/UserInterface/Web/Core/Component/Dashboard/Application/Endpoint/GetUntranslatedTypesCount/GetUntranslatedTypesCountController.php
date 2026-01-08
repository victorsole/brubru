<?php

namespace WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetUntranslatedTypesCount;

use WPML\Core\Component\Translation\Application\Repository\SettingsRepository;
use WPML\Core\Port\Endpoint\EndpointInterface;
use WPML\Core\SharedKernel\Component\Item\Application\Query\UntranslatedTypesCountQueryInterface;

class GetUntranslatedTypesCountController implements EndpointInterface {

  /** @var UntranslatedTypesCountQueryInterface[] */
  private $queries;

  /** @var SettingsRepository */
  private $translationSettingsRepository;


  /**
   * @param UntranslatedTypesCountQueryInterface[] $queries
   */
  public function __construct( array $queries, SettingsRepository $translationSettingsRepository ) {
    $this->queries = $queries;
    $this->translationSettingsRepository = $translationSettingsRepository;
  }


  public function handle( $requestData = null ): array {
    $editorSettings = $this->translationSettingsRepository->getSettings()->getTranslationEditor();
    $queryData = [];
    $queryData['nativeEditorGlobalSetting'] = $editorSettings && $editorSettings->useNativeEditorForAllPostTypes();
    $queryData['nativeEditorSettingPerType'] = $editorSettings ? $editorSettings->getPostTypesUsingNativeEditor() : [];
    $counts = [];

    foreach ( $this->queries as $query ) {
      $counts = array_merge( $counts, $query->get( $queryData ) );
    }

    return array_map(
      function ( $count ) {
        return $count->toArray();
      },
      $counts
    );
  }


}
