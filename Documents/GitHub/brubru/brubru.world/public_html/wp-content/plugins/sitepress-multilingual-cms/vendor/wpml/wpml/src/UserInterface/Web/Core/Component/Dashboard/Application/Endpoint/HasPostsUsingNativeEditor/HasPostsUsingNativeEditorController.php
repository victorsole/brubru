<?php

namespace WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\HasPostsUsingNativeEditor;

use WPML\Core\Component\Translation\Application\Query\HasPostsUsingNativeEditorQueryInterface;
use WPML\Core\Component\Translation\Application\Repository\SettingsRepository;
use WPML\Core\Port\Endpoint\EndpointInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\SharedKernel\Component\Post\Application\Query\Dto\PostTypeDto;
use WPML\Core\SharedKernel\Component\Post\Application\Query\TranslatableTypesQueryInterface;

class HasPostsUsingNativeEditorController implements EndpointInterface {

  /** @var SettingsRepository */
  private $translationSettingsRepository;

  /** @var HasPostsUsingNativeEditorQueryInterface */
  private $query;

  /** @var TranslatableTypesQueryInterface */
  private $translatableTypesQuery;

  /** @var string[] | null */
  private $translatablePostTypes;


  public function __construct(
    SettingsRepository $translationSettingsRepository,
    TranslatableTypesQueryInterface $translatableTypesQuery,
    HasPostsUsingNativeEditorQueryInterface $query
  ) {
    $this->translationSettingsRepository = $translationSettingsRepository;
    $this->translatableTypesQuery = $translatableTypesQuery;
    $this->translatablePostTypes = null;
    $this->query = $query;
  }


  public function handle( $requestData = null ) : array {
    $results = [
      'success' => true,
      'data' => null,
      'errorMsg' => ''
    ];

    $editorSettings = $this->translationSettingsRepository->getSettings()->getTranslationEditor();

    if ( ! $editorSettings ) {
      $results['success'] = false;
      $results['errorMsg'] = 'Error: getTranslationEditor() is not a valid object.';
      return $results;
    }

    $nativeEditorGlobalSetting = $editorSettings->useNativeEditorForAllPostTypes();
    $postTypesSettings = $editorSettings->getPostTypesUsingNativeEditor();

    // If using native editor globally, remove post types those are not using native editor from all
    // translatable post types, so we can treat reaming post types as using native editor.
    // If NOT using native editor globally, only include post types that are using native editor.
    $postTypesUsingWpEditor = $nativeEditorGlobalSetting
      ? array_diff( $this->getTranslatablePostTypes(), $this->getPostTypes( $postTypesSettings, false ) )
      : $this->getPostTypes( $postTypesSettings, true );

    try {
      $results['data'] = $this->query->get(
        $this->getTranslatablePostTypes(),
        $postTypesUsingWpEditor
      );
    } catch ( DatabaseErrorException $exception ) {
      $results['success'] = false;
      $results['errorMsg'] = 'Database Error: ' . $exception->getMessage();
    }

    return $results;
  }


  /**
   * @param array<string, bool> $postTypesSettings
   * @param bool  $usingWpEditor
   *
   * @return string[]
   */
  private function getPostTypes( array $postTypesSettings, bool $usingWpEditor ) : array {
    return array_keys(
      array_filter(
        $postTypesSettings,
        function ( $postTypeValue ) use ( $usingWpEditor ) {
          return $postTypeValue === $usingWpEditor;
        }
      )
    );
  }


  /**
   * @return string[]
   */
  private function getTranslatablePostTypes() : array {
    if ( $this->translatablePostTypes === null ) {
      $this->translatablePostTypes = array_filter(
        array_map(
          function ( PostTypeDto $postType ) {
            // Hardcode "attachment" post, we don't need it.
            return $postType->isPublic() && $postType->hasUi() && $postType->getId() !== 'attachment'
              ? $postType->getId()
              : null;
          },
          $this->translatableTypesQuery->getTranslatable()
        )
      );
    }

    return $this->translatablePostTypes;
  }


}
