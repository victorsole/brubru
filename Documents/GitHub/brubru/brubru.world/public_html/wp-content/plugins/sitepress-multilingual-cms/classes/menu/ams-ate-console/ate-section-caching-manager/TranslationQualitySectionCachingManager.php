<?php

class TranslationQualitySectionCachingManager extends AteSectionCachingManager {

	const CACHE_FILE_NAME = 'translation_quality';
	const CACHE_KEY = self::CACHE_FILE_NAME . '_path';


	public function __construct() {
		$this->cacheKey      = self::CACHE_KEY;
		$this->cacheFileName = self::CACHE_FILE_NAME;
	}

}
