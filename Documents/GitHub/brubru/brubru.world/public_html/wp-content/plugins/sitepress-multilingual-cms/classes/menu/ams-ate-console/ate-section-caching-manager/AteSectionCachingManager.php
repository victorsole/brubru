<?php

abstract class AteSectionCachingManager implements AteSectionCachingManagerInterface {

	/** @var string */
	protected $cacheKey;

	/** @var string */
	protected $cacheFileName;


	/**
	 * @param array $amsConstructor
	 *
	 * @return false|array{
	 *     app: string,
	 *     constructor: string,
	 *     headers: string[],
	 *     isJs: bool,
	 *     errors: string[]
	 * }
	 */
	public function getCachedAppData( $amsConstructor ) {
		$filePath = get_transient( $this->cacheKey );

		if ( $filePath && file_exists( $filePath ) ) {
			$errors = [];

			$app         = file_get_contents( $filePath );
			$constructor = wp_json_encode( $amsConstructor );

			if ( ! $app || ! trim( $app ) ) {
				$errors[] = 'Empty response when retrieving the ATE Widget App';
			}

			$headers = [
				$_SERVER['SERVER_PROTOCOL'] . ' ' . '200 OK',
				'content-type: application/javascript'
			];

			return [
				'app'         => $app,
				'constructor' => $constructor,
				'headers'     => $headers,
				'isJs'        => true,
				'errors'      => $errors,
				'response'    => [],
			];
		}

		return false;
	}

	/**
	 * Checks if there is cached app content available
	 *
	 * @return bool True if cached app content exists, false otherwise
	 */
	public function hasCachedApp() {
		$filePath = get_transient( $this->cacheKey );

		return $filePath && file_exists( $filePath );
	}

	/**
	 * @param string $appContent
	 * @param int $refreshCacheIn Represents in how many hours the cache should be refreshed
	 *
	 * @return string cached file path
	 */
	public function cacheApp( $appContent, $refreshCacheIn = 1 ) {
		$cacheDir = CacheDirectory::get();

		if ( ! file_exists( $cacheDir ) ) {
			wp_mkdir_p( $cacheDir );
		}

		$cacheFilePath = $cacheDir . sanitize_file_name( $this->cacheFileName ) . '.js';
		file_put_contents( $cacheFilePath, $appContent );

		set_transient( $this->cacheKey, $cacheFilePath, $refreshCacheIn * HOUR_IN_SECONDS );

		return $cacheFilePath;
	}

}
