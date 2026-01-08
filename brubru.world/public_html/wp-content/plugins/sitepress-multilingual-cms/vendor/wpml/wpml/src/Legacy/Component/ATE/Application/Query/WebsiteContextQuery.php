<?php

namespace WPML\Legacy\Component\ATE\Application\Query;

use WPML\Core\Component\ATE\Application\Query\Dto\WebsiteContextDto;
use WPML\Core\Component\ATE\Application\Query\WebsiteContextException;
use WPML\Core\Component\ATE\Application\Query\WebsiteContextQueryInterface;
use WPML\TM\API\ATE\WebsiteContext;

/**
 * @phpstan-type WebsiteContextArray array{
 *    context_present: bool,
 *    last_sync?: string|null,
 *    context?: string|null,
 *    language_iso?: string|null,
 *    site_topic?: string|null,
 *    site_purpose?: string|null,
 *    site_audience? : string|null,
 *    status?: string|null,
 *    translate_names?: int|null
 *  }
 *
 *  @phpstan-type WebsiteContextErrorArray array{
 *    error: string,
 *  }
 */

class WebsiteContextQuery implements WebsiteContextQueryInterface {


  public function getWebsiteContext(): WebsiteContextDto {

    $apiResult = WebsiteContext::getWebsiteContext();
    if ( array_key_exists( 'error', (array) $apiResult ) ) {
      /** @var WebsiteContextErrorArray $apiResult */
      throw new WebsiteContextException( $apiResult['error'] );
    }

    /** @var WebsiteContextArray $apiResult */
    return new WebsiteContextDto(
      $apiResult['context_present'],
      $apiResult['last_sync'] ?? null,
      $apiResult['context'] ?? '',
      $apiResult['language_iso'] ?? '',
      $apiResult['site_topic'] ?? '',
      $apiResult['site_purpose'] ?? '',
      $apiResult['site_audience'] ?? '',
      $apiResult['status'] ?? '',
      $apiResult['translate_names'] ?? 0
    );
  }


  public function isContextPresent(): bool {
    try {
        return $this->getWebsiteContext()->isContextPresent();
    } catch ( WebsiteContextException $e ) {
        return false;
    }
  }


}
