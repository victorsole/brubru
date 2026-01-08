<?php

class CacheDirectory {

	public static function get() {
		$uploadDir = wp_upload_dir();

		return $uploadDir['basedir'] . '/wpml-ate-app-cache/';
	}

}
