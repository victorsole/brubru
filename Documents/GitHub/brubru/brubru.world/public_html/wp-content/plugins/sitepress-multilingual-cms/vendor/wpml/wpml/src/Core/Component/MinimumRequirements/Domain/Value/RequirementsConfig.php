<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Value;

/**
 * Value object containing all minimum requirements values.
 *
 * This class centralizes all minimum requirement values used across
 * the system to ensure consistency and easier maintenance.
 */
class RequirementsConfig {

  /**
   * Memory requirements
   */
  const MINIMUM_MEMORY = '128M';
  const WP_MAX_MEMORY_LIMIT = '256M';

  /**
   * Database version requirements
   */
  const MINIMUM_MYSQL_VERSION = '5.6';
  const MINIMUM_MARIADB_VERSION = '10.1';

  /**
   * PHP version requirement
   */
  const MINIMUM_PHP_VERSION = '7.0';

  /**
   * WordPress version requirement
   */
  const MINIMUM_WP_VERSION = '6.0.0';

  /**
   * Stack size requirements (in KB)
   */
  const MINIMUM_AVAILABLE_STACK_SIZE = 208;
  const MINIMUM_MAX_STACK_SIZE = 256;
  const MINIMUM_RESERVED_STACK_SIZE = 48;

  /**
   * XML requirements
   */
  const MINIMUM_LIBXML_VERSION = '2.7.8';
  const MINIMUM_SIMPLEXML_VERSION = '2.7.8';


}
