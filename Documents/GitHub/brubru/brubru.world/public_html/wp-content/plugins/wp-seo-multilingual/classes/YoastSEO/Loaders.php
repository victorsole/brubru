<?php

namespace WPML\WPSEO\YoastSEO;

use WPML\FP\Logic;

class Loaders {

	/**
	 * @param string $wpSeoVersion
	 *
	 * @return array
	 */
	public static function get( $wpSeoVersion ) {
		$isSitemapHrefLangEnabled = ! defined( 'WPML_SEO_ENABLE_SITEMAP_HREFLANG' ) || constant( 'WPML_SEO_ENABLE_SITEMAP_HREFLANG' );
		$isSTEnabled              = defined( 'WPML_ST_VERSION' );
		$isWPSEONewsEnabled       = defined( 'WPSEO_NEWS_VERSION' );
		$isGTEVersion14           = version_compare( $wpSeoVersion, '14', '>=' );
		$isWPSEOPremium           = Utils::isPremium();

		return wpml_collect(
			[
				\WPML\WPSEO\Shared\Upgrade\Hooks::class => true,
				\WPML\WPSEO\Shared\Localization::class  => true,
				\WPML_WPSEO_Main_Factory::class         => true,
				PrimaryCategory\Hooks::class            => true,
				Terms\AdminHooks::class                 => true,
				Terms\Meta\Hooks::class                 => true,
				TranslationJob\Hooks::class             => true,
				Sitemap\Cache::class                    => true,
				Sitemap\AlternateLangHooks::class       => $isSitemapHrefLangEnabled,
				SlugTranslation\Hooks::class            => $isSTEnabled,
				Addons\WPSEONews\Sitemap\Hooks::class   => $isWPSEONewsEnabled,
				Presentation\Hooks::class               => $isGTEVersion14,
				Meta\SocialHooks::class                 => $isGTEVersion14,
				Indexable\Hooks::class                  => $isGTEVersion14,
				Redirects\Hooks::class                  => $isWPSEOPremium,
			]
		)->filter( Logic::isTruthy() )
			->keys()
			->toArray();
	}
}
