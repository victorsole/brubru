<?php

namespace WPML\Core\SharedKernel\Component\Server\Domain;

/**
 * Interface for retrieving server information.
 */
interface ServerInfoInterface {


  /**
   * Get PHP version information.
   *
   * @return string The PHP version
   */
  public function getPhpVersion(): string;


  /**
   * Get the database version.
   *
   * @return string|null The database version
   */
  public function getDbVersion();


  /**
   * Get the current runtime value of a PHP setting. It could be changed at runtime
   *
   * @param string $key The name of the INI setting to retrieve
   *
   * @return string|false The value of the INI setting
   */
  public function getIniGet( string $key );


  /**
   * Read the original value from php.ini even if it changed later.
   *
   * @param string $key
   *
   * @return string|false The value of the INI setting
   */
  public function getOriginalIniGet( string $key );


  /**
   * Get the WordPress version.
   *
   * @return string The WordPress version
   */
  public function getWordPressVersion(): string;


  /**
   * Get the value of a PHP constant.
   *
   * @param string $name    The name of the constant to retrieve
   * @param mixed  $default The default value to return if the constant is not defined
   *
   * @return mixed The value of the constant or the default value
   */
  public function getConstant( string $name, $default = null );


  /**
   * Check if a PHP extension is loaded.
   *
   * @param string $name The name of the extension to check
   *
   * @return bool True if the extension is loaded, false otherwise
   */
  public function isExtensionLoaded( string $name ): bool;


}
