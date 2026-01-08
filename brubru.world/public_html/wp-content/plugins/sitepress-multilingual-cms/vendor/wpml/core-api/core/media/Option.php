<?php

namespace WPML\Media;

use WPML\FP\Obj;
use WPML\FP\Cast;
use WPML\LIB\WP\Option as WPOption;
use WPML\LIB\WP\Post;

class Option {
	const OPTION_KEY = '_wpml_media';

	const DUPLICATE_MEDIA_KEY = '_wpml_media_duplicate';
	const DUPLICATE_FEATURED_KEY = '_wpml_media_featured';

	const SETUP_FINISHED = 'starting_help';

	const SHOULD_HANDLE_MEDIA_AUTO_KEY = 'should_handle_media_auto';
	const SHOULD_SHOW_HANDLE_MEDIA_AUTO_BANNER_AFTER_UPGRADE = 'should_show_handle_media_auto_banner_after_upgrade';
	const SHOULD_SHOW_HANDLE_MEDIA_AUTO_NOTICE_30_DAYS_AFTER_UPGRADE = 'should_show_handle_media_auto_notice_30_days_after_upgrade';
	const IS_ADMIN_NOTICE_FOR_ELEMENTOR_ON_MT_HOMEPAGE_DISMISSED = 'is_admin_notice_for_elementor_on_mt_homepage_dismissed';

	/**
	 * This makes sure that the option '_wpml_media' is written to the database.
	 * This is required because after the WPML setup there are parallel ajax calls,
	 * which can lead having the '_wpml_media' in the WP "notoptions" cache key, while
	 * the set options call ran in a parallel and writes when "notoptions" isn't set,
	 * so it never gets cleared. In that case the "Calculation..." of automatic
	 * translation will never start as the media setup does not finish.
	 *
	 * Note: This only happens when persistent object caching (Redis) is active.
	 *
	 * @return void
	 */
	public static function prepareSetup() {
		$option = WPOption::getOr( self::OPTION_KEY, false );
		if ( $option === false ) {
			WPOption::updateWithoutAutoLoad( self::OPTION_KEY, [] );
		}
	}

	public static function isSetupFinished() {
		return self::get( self::SETUP_FINISHED );
	}

	public static function setSetupFinished( $setupFinished = true ) {
		self::set( self::SETUP_FINISHED, $setupFinished );
	}

	/**
	 * It gets default setting for new content creation.
	 * It determines if media should be translated, duplicated or not.
	 *
	 * @return array{always_translate_media: bool, duplicate_media: bool, duplicate_featured: bool}
	 */
	public static function getNewContentSettings() {
		$data = self::get( 'new_content_settings', [
			'always_translate_media' => true,
			'duplicate_media'        => true,
			'duplicate_featured'     => true,
		] );

		return Obj::evolve( [
			'always_translate_media' => Cast::toBool(),
			'duplicate_media'        => Cast::toBool(),
			'duplicate_featured'     => Cast::toBool(),
		], $data );
	}

	/**
	 * @param array{always_translate_media: bool, duplicate_media: bool, duplicate_featured: bool} $settings
	 *
	 * @return void
	 */
	public static function setNewContentSettings( array $settings ) {
		$settings = Obj::pick( [ 'always_translate_media', 'duplicate_media', 'duplicate_featured' ], $settings );
		$settings = Obj::evolve( [
			'always_translate_media' => Cast::toBool(),
			'duplicate_media'        => Cast::toBool(),
			'duplicate_featured'     => Cast::toBool(),
		], $settings );

		self::set( 'new_content_settings', $settings );
	}

	/**
	 * @param int $postId
	 * @param bool $useGlobalSettings
	 *
	 * @return bool|null
	 */
	public static function shouldDuplicateMedia( $postId, $useGlobalSettings = true ) {
		if ( self::shouldHandleMediaAuto() ) {
			return false;
		}

		$individualValue = Post::getMetaSingle( $postId, self::DUPLICATE_MEDIA_KEY );

		$isNotDefined = $individualValue === '' || $individualValue === null;
		if ( $isNotDefined && ! $useGlobalSettings ) {
			return null;
		}

		if ( $isNotDefined ) {
			return (bool) Obj::propOr( true, 'duplicate_media', self::getNewContentSettings() );
		}

		return (bool) $individualValue;
	}

	/**
	 * @param int $postId
	 * @param bool $useGlobalSettings
	 *
	 * @return bool|null
	 */
	public static function shouldDuplicateFeatured( $postId, $useGlobalSettings = true ) {
		if ( self::shouldHandleMediaAuto() ) {
			return false;
		}

		$individualValue = Post::getMetaSingle( $postId, self::DUPLICATE_FEATURED_KEY );

		$isNotDefined = $individualValue === '' || $individualValue === null;
		if ( $isNotDefined && ! $useGlobalSettings ) {
			return null;
		}

		if ( $isNotDefined ) {
			return (bool) Obj::propOr( true, 'duplicate_featured', self::getNewContentSettings() );
		}

		return (bool) $individualValue;
	}

	/**
	 * @param int $postId
	 * @param bool $flag
	 */
	public static function setDuplicateMediaForIndividualPost( $postId, $flag ) {
		Post::updateMeta( $postId, self::DUPLICATE_MEDIA_KEY, $flag ? 1 : 0 );
	}

	/**
	 * @param int $postId
	 * @param bool $flag
	 */
	public static function setDuplicateFeaturedForIndividualPost( $postId, $flag ) {
		Post::updateMeta( $postId, self::DUPLICATE_FEATURED_KEY, $flag ? 1 : 0 );
	}

	/**
	 * @param bool $flag
	 *
	 * @return void
	 */
	public static function setTranslateMediaLibraryTexts( $flag ) {
		self::set( 'translate_media_library_texts', (bool) $flag );
	}

	/**
	 * @return bool
	 */
	public static function getTranslateMediaLibraryTexts() {
		return (bool) self::get( 'translate_media_library_texts', false );
	}

	/**
	 * @param bool $flag
	 *
	 * @return void
	 */
	public static function setShouldHandleMediaAuto( $flag ) {
		self::set( self::SHOULD_HANDLE_MEDIA_AUTO_KEY, (bool) $flag );
	}

	/**
	 * @return bool
	 */
	public static function shouldHandleMediaAuto() {
		return (bool) self::get( self::SHOULD_HANDLE_MEDIA_AUTO_KEY, false );
	}

	public static function setShouldShowHandleMediaAutoBannerAfterUpgrade() {
		self::set( self::SHOULD_SHOW_HANDLE_MEDIA_AUTO_BANNER_AFTER_UPGRADE, 1 );
	}

	public static function setShouldShowHandleMediaAutoNotice30DaysAfterUpgrade() {
		self::set( self::SHOULD_SHOW_HANDLE_MEDIA_AUTO_NOTICE_30_DAYS_AFTER_UPGRADE, time() );
	}

	public static function setIsAdminNoticeForElementorOnMtHomepageDismissed() {
		self::set( self::IS_ADMIN_NOTICE_FOR_ELEMENTOR_ON_MT_HOMEPAGE_DISMISSED, 1 );
	}

	public static function removeShouldShowHandleMediaAutoBannerAfterUpgrade() {
		self::remove( self::SHOULD_SHOW_HANDLE_MEDIA_AUTO_BANNER_AFTER_UPGRADE );
	}

	public static function removeShouldShowHandleMediaAutoNotice30DaysAfterUpgrade() {
		self::remove( self::SHOULD_SHOW_HANDLE_MEDIA_AUTO_NOTICE_30_DAYS_AFTER_UPGRADE );
	}

	public static function removeIsAdminNoticeForElementorOnMtHomepageDismissed() {
		self::remove( self::IS_ADMIN_NOTICE_FOR_ELEMENTOR_ON_MT_HOMEPAGE_DISMISSED );
	}

	/**
	 * @return boolean
	 */
	public static function shouldShowHandleMediaAutoBannerAfterUpgrade() {
		return self::get( self::SHOULD_SHOW_HANDLE_MEDIA_AUTO_BANNER_AFTER_UPGRADE, null ) !== null;
	}

	/**
	 * @return boolean
	 */
	public static function isAdminNoticeForElementorOnMtHomepageDismissed() {
		return self::get( self::IS_ADMIN_NOTICE_FOR_ELEMENTOR_ON_MT_HOMEPAGE_DISMISSED, null ) !== null;
	}

	/**
	 * @return boolean
	 */
	public static function shouldShowHandleMediaAutoNotice30DaysAfterUpgrade() {
		$startTime = self::get( self::SHOULD_SHOW_HANDLE_MEDIA_AUTO_NOTICE_30_DAYS_AFTER_UPGRADE, null );
		if ( is_null( $startTime ) ) {
			return false;
		}

		$startTime = (int) $startTime;

		return ( time() - $startTime ) >= 30 * DAY_IN_SECONDS;
	}

	private static function get( $name, $default = false ) {
		return Obj::propOr( $default, $name, WPOption::getOr( self::OPTION_KEY, [] ) );
	}

	private static function set( $name, $value ) {
		$data          = WPOption::getOr( self::OPTION_KEY, [] );
		$data[ $name ] = $value;

		WPOption::updateWithoutAutoLoad( self::OPTION_KEY, $data );
	}

	/**
	 * @param string $name
	 */
	private static function remove( $name ) {
		$data = WPOption::getOr( self::OPTION_KEY, [] );
		unset( $data[ $name ] );

		WPOption::updateWithoutAutoLoad( self::OPTION_KEY, $data );
	}
}
