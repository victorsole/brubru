<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\Component\MinimumRequirements\Domain\Value\RequirementsConfig;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;

class PHPVersionRequirement extends RequirementBase {

  /** @var ServerInfoInterface  */
  private $serverInfo;


  public function __construct( ServerInfoInterface $server_info ) {
    $this->serverInfo = $server_info;
  }


  public function getId(): int {
    return 2;
  }


  public function getTitle(): string {
    return __( 'PHP Version', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'Your PHP version is outdated. WPML requires at least %s.',
            'wpml'
          ),
          '<strong>PHP '.RequirementsConfig::MINIMUM_PHP_VERSION.'</strong>'
        ),
      ],
      [
        'type'    => 'alert',
        'message' => sprintf(
          __(
            'Contact your hosting provider to upgrade PHP to version %s or higher.',
            'wpml'
          ),
          RequirementsConfig::MINIMUM_PHP_VERSION
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    return version_compare(
      $this->serverInfo->getPhpVersion(),
      RequirementsConfig::MINIMUM_PHP_VERSION,
      '>='
    );
  }


  protected function getRequirementType(): string {
    return 'PHP_VERSION';
  }


}
