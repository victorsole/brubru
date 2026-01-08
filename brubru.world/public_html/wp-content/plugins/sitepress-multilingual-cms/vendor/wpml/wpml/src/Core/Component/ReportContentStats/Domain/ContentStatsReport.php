<?php

namespace WPML\Core\Component\ReportContentStats\Domain;

/**
 * @phpstan-type LanguageInfo array{
 *   code: string,
 *   defaultLocale: string,
 *   nativeName: string,
 *   englishName: string,
 *   displayName: string,
 * }
 *
 * @phpstan-type ContentStatsArray array<string, array{
 *   postsCount: int,
 *   charactersCount: int,
 *   translationCoverage: array<string, float|int>
 * }>
 */
class ContentStatsReport {

  /** @var string|false */
  private $siteKey;

  /** @var string */
  private $siteUrl;

  /** @var string */
  private $currentTranslationEditor;

  /** @phpstan-var LanguageInfo */
  private $defaultLanguage;

  /** @phpstan-var LanguageInfo[] */
  private $translationLanguages;

  /** @var string|null */
  private $siteUUID;

  /** @var string|null */
  private $siteSharedKey;

  /** @phpstan-var ContentStatsArray */
  private $contentStats;


  /**
   * @param string|false $siteKey
   * @param string $siteUrl
   * @param string $currentTranslationEditor
   * @param string|null $siteUUID
   * @param string|null $siteSharedKey
   *
   * @phpstan-param LanguageInfo $defaultLanguage
   * @phpstan-param LanguageInfo[] $translationLanguages
   * @phpstan-param ContentStatsArray $contentStats
   */
  public function __construct(
    $siteKey,
    string $siteUrl,
    string $currentTranslationEditor,
    array $defaultLanguage,
    array $translationLanguages,
    $siteUUID,
    $siteSharedKey,
    array $contentStats
  ) {
    $this->siteKey                  = $siteKey;
    $this->siteUrl                  = $siteUrl;
    $this->currentTranslationEditor = $currentTranslationEditor;
    $this->defaultLanguage          = $defaultLanguage;
    $this->translationLanguages     = $translationLanguages;
    $this->siteUUID                 = $siteUUID;
    $this->siteSharedKey            = $siteSharedKey;
    $this->contentStats             = $contentStats;
  }


  /**
   * @phpstan-return  array{
   *   siteKey: string|false,
   *   siteUrl: string,
   *   currentTranslationEditor: string,
   *   defaultLanguage: LanguageInfo,
   *   translationLanguages: LanguageInfo[],
   *   siteUUID: string|null,
   *   siteSharedKey: string|null,
   *   contentStats: ContentStatsArray,
   * }
   */
  public function getAsArray(): array {
    return [
      'siteKey'                  => $this->siteKey,
      'siteUrl'                  => $this->siteUrl,
      'currentTranslationEditor' => $this->currentTranslationEditor,
      'siteUUID'                 => $this->siteUUID,
      'siteSharedKey'            => $this->siteSharedKey,
      'defaultLanguage'          => $this->defaultLanguage,
      'translationLanguages'     => $this->translationLanguages,
      'contentStats'             => $this->contentStats,
    ];
  }


  /** @return string|false */
  public function getSiteKey() {
    return $this->siteKey;
  }


  public function getCurrentTranslationEditor(): string {
    return $this->currentTranslationEditor;
  }


  /**
   * @phpstan-return LanguageInfo
   */
  public function getDefaultLanguage(): array {
    return $this->defaultLanguage;
  }


  /**
   * @phpstan-return LanguageInfo[]
   */
  public function getTranslationLanguages(): array {
    return $this->translationLanguages;
  }


  /**
   * @return string|null
   */
  public function getSiteUUID() {
    return $this->siteUUID;
  }


  /**
   * @return string|null
   */
  public function getSiteSharedKey() {
    return $this->siteSharedKey;
  }


  /**
   * @phpstan-return ContentStatsArray
   */
  public function getContentStats(): array {
    return $this->contentStats;
  }


}
