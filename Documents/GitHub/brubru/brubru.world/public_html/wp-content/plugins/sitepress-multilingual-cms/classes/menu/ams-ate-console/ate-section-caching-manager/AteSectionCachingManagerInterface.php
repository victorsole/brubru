<?php

interface AteSectionCachingManagerInterface {

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
	public function getCachedAppData( $amsConstructor );

	/**
	 * @param string $appContent
	 * @param int $invalidateIn
	 *
	 * @return string cached file path
	 */
	public function cacheApp( $appContent, $invalidateIn = 1 );
}
