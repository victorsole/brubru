<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\Component\MinimumRequirements\Domain\Value\RequirementsConfig;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;
use WPML\Core\SharedKernel\Component\Server\Domain\Service\ByteSizeConverter;

class StackSizeRequirement extends RequirementBase {

  /** @var ServerInfoInterface */
  private $serverInfo;

  /** @var ByteSizeConverter */
  private $byteSizeConverter;

  const BYTES_PER_KB = 1024;


  /**
   * Constructor.
   *
   * @param ServerInfoInterface $serverInfo The server info service.
   */
  public function __construct(
    ServerInfoInterface $serverInfo, ByteSizeConverter $byteSizeConverter
  ) {
    $this->serverInfo        = $serverInfo;
    $this->byteSizeConverter = $byteSizeConverter;
  }


  public function getId(): int {
    return 10;
  }


  public function getTitle(): string {
    return __( 'PHP Stack Size', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'WPML requires at least %s KB of PHP stack size on PHP 8.3 or higher.',
            'wpml'
          ),
          RequirementsConfig::MINIMUM_AVAILABLE_STACK_SIZE
        ),
      ],
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'Add this to your %sphp.ini%s and restart your web server to set the required stack size:',
            'wpml'
          ),
          '<strong>',
          '</strong>'
        ),
      ],
      [
        'type'    => 'code',
        'message' => "; Stack Size Configuration\nzend.max_allowed_stack_size = "
                     . RequirementsConfig::MINIMUM_MAX_STACK_SIZE
                     . "K\nzend.reserved_stack_size = "
                     . RequirementsConfig::MINIMUM_RESERVED_STACK_SIZE . "K",
      ]
    ];
  }


  protected function getRequirementType(): string {
    return 'STACK_SIZE';
  }


  protected function doIsValid(): bool {
    if ( version_compare( $this->serverInfo->getPhpVersion(), '8.3', '<' ) ) {
      return true;
    }

    // Calculate available stack size
    $availableStack = $this->calculateAvailableStackSize();

    return $availableStack >= RequirementsConfig::MINIMUM_AVAILABLE_STACK_SIZE
                              * self::BYTES_PER_KB;
  }


  /**
   * @return int The available stack size in bytes
   */
  private function calculateAvailableStackSize(): int {
    return $this->getMaxAllowedStackSize() - $this->getReservedStackSize();
  }


  /**
   * @return int The max allowed stack size in bytes
   */
  private function getMaxAllowedStackSize(): int {
    // According to PHP documentation, possible values are:
    // 0 (auto-detect), -1 (unlimited), or a positive number of bytes
    $value = $this->serverInfo->getIniGet( 'zend.max_allowed_stack_size' );

    if ( ! $value ) {
      $value = 0; //default value of PHP
    }

    $valueInBytes = $this->byteSizeConverter->toBytes( $value );
    if ( $valueInBytes === - 1 || $valueInBytes === 0 ) {
      return PHP_INT_MAX;
    } else {
      return $valueInBytes;
    }
  }


  /**
   * @return int The reserved stack size in bytes
   */
  private function getReservedStackSize(): int {
    $value = $this->serverInfo->getIniGet( 'zend.reserved_stack_size' );

    if ( ! $value ) {
      $value = 0; //default value of PHP
    }

    // Reserved stack size is always expressed in bytes
    // The value -1 is not allowed, so we'll default to 0 if it's negative
    return max( 0, $this->byteSizeConverter->toBytes( $value ) );
  }


}
