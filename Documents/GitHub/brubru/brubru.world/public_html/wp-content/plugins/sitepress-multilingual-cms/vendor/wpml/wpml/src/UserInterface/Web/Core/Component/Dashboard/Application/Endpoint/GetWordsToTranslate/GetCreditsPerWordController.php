<?php

namespace WPML\UserInterface\Web\Core\Component\Dashboard\Application\Endpoint\GetWordsToTranslate;

use WPML\Core\Component\WordsToTranslate\Application\Service\WordsToTranslateService;
use WPML\Core\Port\Endpoint\EndpointInterface;
use WPML\PHP\Exception\RuntimeException;

class GetCreditsPerWordController implements EndpointInterface {

  /** @var WordsToTranslateService */
  private $wordsToTranslateService;


  public function __construct( WordsToTranslateService $wordsToTranslateServices ) {
    $this->wordsToTranslateService = $wordsToTranslateServices;
  }


  /**
   * Handles the request to get credits per word for specified languages.
   *
   * @param array<string, mixed>|null $requestData
   *
   * @return array<string, int|false>
   *
   * @throws RuntimeException Engines couldn't be fetched from AMS API.
   */
  public function handle( $requestData = null ): array {
    $langs = $requestData['langs'] ?? [];
    $sourceLang = isset( $requestData['langFrom'] ) && is_string( $requestData['langFrom' ] )
      ? $requestData['langFrom']
      : '';

    $creditsPerWord = [];

    if ( ! is_array( $langs ) || empty( $langs ) ) {
      return [];
    }

    foreach ( $langs as $lang ) {
      try {
        if ( ! is_string( $lang ) || empty( $lang ) ) {
          continue;
        }
        $creditsPerWord[ $lang ] = $this->wordsToTranslateService->getCostsPerWordForLang( $lang, $sourceLang );
      } catch ( RuntimeException $e ) {
        // Treat it as no translation engine available for this language.
        $creditsPerWord[ $lang ] = false;
        continue;
      }
    }

    return $creditsPerWord;
  }


}
