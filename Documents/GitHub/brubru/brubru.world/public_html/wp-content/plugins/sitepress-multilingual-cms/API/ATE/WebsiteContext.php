<?php

namespace WPML\TM\API\ATE;

use WPML\FP\Either;
use WPML\FP\Fns;
use WPML\LIB\WP\WordPress;
use function WPML\Container\make;

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
class WebsiteContext {

	/**
	 * @return WebsiteContextArray|WebsiteContextErrorArray
	 */
	public static function getWebsiteContext() {
		$websiteContext = make( \WPML_TM_ATE_API::class )->get_website_context();

		if ( $websiteContext instanceof \WP_Error ) {
			return [
				'error' => $websiteContext->get_error_message(),
			];
		}

		return (array) $websiteContext;
	}
}
