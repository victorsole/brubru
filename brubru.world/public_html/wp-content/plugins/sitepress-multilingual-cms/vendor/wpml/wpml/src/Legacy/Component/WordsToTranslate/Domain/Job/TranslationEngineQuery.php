<?php

// phpcs:ignoreFile Squiz.NamingConventions.ValidVariableName.MemberNotCamelCaps
namespace WPML\Legacy\Component\WordsToTranslate\Domain\Job;

use WPML\Core\Component\WordsToTranslate\Domain\Job\Query\TranslationEngineQueryInterface;
use WPML\PHP\Exception\InvalidArgumentException;
use WPML\PHP\Exception\RuntimeException;
use WPML\Element\API\Languages;

// Legacy
use WPML\TM\API\ATE\CachedLanguageMappings;
use WPML\TM\ATE\API\CacheStorage\Transient;
use WPML\TM\ATE\API\CachedAMSAPI;
use function WPML\Container\make;

class TranslationEngineQuery implements TranslationEngineQueryInterface {

  /** @var ?CachedAMSAPI */
  private $_amsApi;

  /** @var ?array<string, string> */
  private $languages;

  /** @var ?array<string, int> */
  private $engines;

  /**
   * Returns the AMS API instance, cached for performance.
   *
   * @return CachedAMSAPI
   */
  private function amsApi() {
    if ( $this->_amsApi === null ) {
      $this->_amsApi =
        new CachedAMSAPI(
          make( \WPML_TM_AMS_API::class ),
          new Transient()
        );
    }

    return $this->_amsApi;
  }


  /**
   * Returns the cost per word for the given language code.
   *
   * @param string $langCode
   * @param ?string $sourceLang
   *
   * @return int|false
   *
   * @throws RuntimeException Could not fetch engines from AMS API.
   */
  public function getCostsPerWordForLang( string $langCode, $sourceLang = null ) {
    $languages = $this->getLanguages( $sourceLang );

    if ( ! array_key_exists( $langCode, $languages ) ) {
      return false;
    }

    $engines = $this->getEngines();
    $languageEngine = $languages[ $langCode ];

    if ( ! array_key_exists( $languageEngine, $engines ) ) {
      // No available translation engine for the language.
      return false;
    }

    return $engines[ $languageEngine ];
  }


  /**
   * Returns the list of languages that can be translated automatically.
   *
   * @param ?string $sourceLang
   *
   * @return array<string, string>
   */
  private function getLanguages( $sourceLang = null) {
    if ( $this->languages !== null ) {
      return $this->languages;
    }
    $this->languages = [];

    $languages = CachedLanguageMappings::getAllLanguagesWithAutomaticSupportInfo(
      $sourceLang
    );

    if ( ! is_array( $languages ) ) {
      return $this->languages;
    }

    foreach ( $languages as $langCode => $language ) {
      if (
        ! is_array( $language )
        || ! array_key_exists( 'can_be_translated_automatically', $language )
        || ! array_key_exists( 'engine', $language )
      ) {
        continue;
      }

      if ( $language['can_be_translated_automatically'] ) {
        $this->languages[ $langCode ] = $language['engine'];
      }
    }

    return $this->languages;
  }


  /**
   * @return array<string, int>
   *
   * @throws RuntimeException
   */
  private function getEngines() {
    if ( $this->engines !== null ) {
      return $this->engines;
    }

    $engines = $this->amsApi()->get_translation_engines();

    if ( ! is_array( $engines ) ) {
      throw new RuntimeException(
        'Translation engines are not available. Please check the AMS API.'
      );
    }

    if ( ! array_key_exists( 'list', $engines ) || ! is_array( $engines['list'] ) ) {
      throw new RuntimeException(
        'The return value of \WPML_TMS_API::get_translation_engines() is not valid.'
      );
    }

    $this->engines = [];

    foreach ( $engines['list'] as $engine ) {
      if (
        ! is_array( $engine )
        || ! array_key_exists( 'engine', $engine )
        || ! is_string( $engine['engine'] )
        || ! array_key_exists( 'cost', $engine ) ) {
        continue;
      }
      $this->engines[ $engine['engine'] ] = (int) $engine['cost'];
    }


    return $this->engines;
  }

}
