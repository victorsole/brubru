<?php

namespace WPML\Core\Component\ATE\Application\Query\Dto;

use WPML\PHP\DateTime;

/**
 * @phpstan-type WebsiteContextJsonArray array{
 *    contextPresent: bool,
 *    lastSync: string|null,
 *    context: string|null,
 *    languageIso: string|null,
 *    siteTopic?: string|null,
 *    sitePurpose: string|null,
 *    siteAudience : string|null,
 *    status: string|null,
 *    translateNames: int|null
 *  }
 */

class WebsiteContextDto
{

  /**
   * @var bool
   */
  private $contextPresent;

  /**
   * @var DateTime|false|null
   */
  private $lastSync;

  /**
   * @var string|null
   */
  private $context;

  /**
   * @var string|null
   */
  private $languageIso;

  /**
   * @var string|null
   */
  private $siteTopic;

  /**
   * @var string|null
   */
  private $sitePurpose;

  /**
   * @var string|null
   */
  private $siteAudience;

  /**
   * @var string|null
   */
  private $status;

  /**
   * @var int|null
   */
  private $translateNames;


  public function __construct(
      bool $contextPresent,
      string $lastSync = null,
      string $context = null,
      string $languageIso = null,
      string $siteTopic = null,
      string $sitePurpose = null,
      string $siteAudience = null,
      string $status = null,
      int $translateNames = null
  ) {

    $this->contextPresent = $contextPresent;
    $this->lastSync = $lastSync ? DateTime::createFromFormat( 'Y-m-d\TH:i:s.v\Z' ,$lastSync ) : null;
    $this->context = $context;
    $this->languageIso = $languageIso;
    $this->siteTopic = $siteTopic;
    $this->sitePurpose = $sitePurpose;
    $this->siteAudience = $siteAudience;
    $this->status = $status;
    $this->translateNames = $translateNames;
  }


  public function isContextPresent(): bool {
    return $this->contextPresent;
  }


  /**
   * @return WebsiteContextJsonArray $items
   */
  public function jsonSerialize(): array {
     return [
       'contextPresent' => $this->contextPresent,
       'lastSync' => $this->lastSync ? $this->lastSync->format( 'Y-m-d H:i:s' ) : null,
       'context' => $this->context,
       'languageIso' => $this->languageIso,
       'siteTopic' => $this->siteTopic,
       'sitePurpose' => $this->sitePurpose,
       'siteAudience' => $this->siteAudience,
       'status' => $this->status,
       'translateNames' => $this->translateNames,
     ];
  }


}
