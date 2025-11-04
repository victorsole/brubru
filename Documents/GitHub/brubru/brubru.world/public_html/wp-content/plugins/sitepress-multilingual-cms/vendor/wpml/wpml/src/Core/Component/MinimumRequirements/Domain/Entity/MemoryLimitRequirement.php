<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\Component\MinimumRequirements\Domain\Value\RequirementsConfig;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\Service\ByteSizeConverter;

/**
 * Class MemoryLimitRequirement
 *
 * This class validates if the WordPress memory limit meets WPML minimum requirements.
 * It checks both WP_MEMORY_LIMIT and WP_MAX_MEMORY_LIMIT constants against a predefined
 * minimum value, and provides appropriate messages if the requirements are not met.
 *
 * @package WPML\Core\Component\MinimumRequirements\Domain\Entity
 */
class MemoryLimitRequirement extends RequirementBase {

  /**
   * Server information provider
   *
   * @var ServerInfoInterface
   */
  private $serverInfo;

  /**
   * Size utility
   *
   * @var ByteSizeConverter
   */
  private $converter;


  /**
   * Constructor
   *
   * @param ServerInfoInterface $server_info         The server information interface
   * @param ByteSizeConverter   $byte_size_converter The memory size utility
   */
  public function __construct(
    ServerInfoInterface $server_info, ByteSizeConverter $byte_size_converter
  ) {
    $this->serverInfo = $server_info;
    $this->converter  = $byte_size_converter;
  }


  public function getId(): int {
    return 1;
  }


  public function getTitle(): string {
    return __( 'Memory limit', 'wpml' );
  }


  public function getMessages(): array {
    return [

      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'Your PHP memory limit is currently %s. '
            .
            ' WPML requires at least %s to function properly.',
            'wpml'
          ),
          '<strong>' .
          $this->converter->toBytes( $this->getOriginalPHPMemoryLimit() )
          / ( 1024 * 1024 ) . 'M</strong>',
          '<strong>' . RequirementsConfig::MINIMUM_MEMORY . '</strong>'
        )
      ],
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'To increase the memory limit, add this to the top of your %swp-config.php%s file:',
            'wpml'
          ),
          '<strong>',
          '</strong>'
        )
      ],
      [
        'type'    => 'code',
        'message' => "/** Memory Limit */\ndefine( 'WP_MEMORY_LIMIT', '"
                     . RequirementsConfig::MINIMUM_MEMORY
                     . "' );\ndefine( 'WP_MAX_MEMORY_LIMIT', '"
                     . RequirementsConfig::WP_MAX_MEMORY_LIMIT . "' );",
      ]
    ];
  }


  protected function doIsValid(): bool {
    /**By default, WordPress will attempt to increase the memory allocated to PHP
     * using WP_MEMORY_LIMIT (default value: 40MB) on the frontend
     * or WP_MAX_MEMORY_LIMIT (default value: 256MB) on admin pages,
     * but ONLY if the current PHP memory limit in php.ini is lower than these values.
     **/
    if ( $this->isMemoryLimitValid( $this->getOriginalPHPMemoryLimit() ) ) {
      return true;
    }

    return $this->isMemoryLimitValid( $this->getWPMaxMemoryLimit() )
           && $this->isMemoryLimitValid( $this->getWPMemoryLimit() );
  }


  protected function getRequirementType(): string {
    return 'MEMORY_LIMIT';
  }


  /**
   * Gets the current value of WP_MEMORY_LIMIT constant
   *
   * @return mixed The memory limit value
   */
  private function getWPMemoryLimit() {
    return $this->serverInfo->getConstant( 'WP_MEMORY_LIMIT', '40M' );
  }


  /**
   * Gets the original value of php memory_limit in php.ini
   *
   * @return string The memory limit value
   */
  private function getOriginalPHPMemoryLimit(): string {
    return (string) $this->serverInfo->getOriginalIniGet( 'memory_limit' );
  }


  /**
   * Gets the current value of WP_MAX_MEMORY_LIMIT constant
   *
   * @return mixed The memory limit value
   */
  private function getWPMaxMemoryLimit() {
    return $this->serverInfo->getConstant(
      'WP_MAX_MEMORY_LIMIT',
      '256M'
    );
  }


  /**
   * Checks if the memory limit value is valid
   *
   * @param mixed $memoryLimit The memory limit value to check
   *
   * @return bool True if valid, false otherwise
   */
  private function isMemoryLimitValid( $memoryLimit ): bool {
    if ( ! is_string( $memoryLimit ) && ! is_int( $memoryLimit ) ) {
      return false;
    }

    if ( (int) $memoryLimit === - 1 ) {
      return true;
    }

    return $this->converter->toBytes( $memoryLimit )
           >= $this->converter->toBytes( RequirementsConfig::MINIMUM_MEMORY );
  }


}
