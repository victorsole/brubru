<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\Component\MinimumRequirements\Domain\Value\RequirementsConfig;
use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;

class DatabaseVersionRequirement extends RequirementBase {

  /**
   * @var ServerInfoInterface
   * */
  private $serverInfo;


  public function __construct( ServerInfoInterface $serverInfo ) {
    $this->serverInfo = $serverInfo;
  }


  public function getId(): int {
    return 3;
  }


  public function getTitle(): string {
    return __( 'Database Version', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'Your %sMySQL%s version must be at least %s. '
            .
            'Alternatively, you can use %sMariaDb%s version %s or higher.',
            'wpml'
          ),
          '<strong>',
          '</strong>',
          '<strong>' . RequirementsConfig::MINIMUM_MYSQL_VERSION . '</strong>',
          '<strong>',
          '</strong>',
          RequirementsConfig::MINIMUM_MARIADB_VERSION
        ),
      ],
      [
        'type'    => 'alert',
        'message' => sprintf(
          __(
            'Contact your hosting provider to upgrade MySQL %s or higher.',
            'wpml'
          ),
          RequirementsConfig::MINIMUM_MYSQL_VERSION
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    $dbVersion = $this->serverInfo->getDbVersion();
    if ( empty( $dbVersion ) ) {
      return false;
    }
    if ( $this->usesMariaDB( $dbVersion ) ) {
      return $this->isValidMariaDBVersion( $dbVersion );
    } else {
      // MySQL
      return $this->isValidMySQLVersion( $dbVersion );
    }
  }


  protected function getRequirementType(): string {
    return 'DATABASE_VERSION';
  }


  private function usesMariaDB( string $version ): bool {
    return stripos( $version, 'mariadb' ) !== false;
  }


  private function isValidMariaDBVersion( string $version ): bool {
    preg_match( '/([\d.]+)-MariaDB/i', $version, $matches );
    $db_version = $matches[1] ?? '';

    if ( empty( $db_version ) ) {
      return false;
    }

    return version_compare(
      $db_version,
      RequirementsConfig::MINIMUM_MARIADB_VERSION,
      '>='
    );
  }


  private function isValidMySQLVersion( string $version ): bool {
    preg_match( '/([0-9]+\.[0-9]+(?:\.[0-9]+)?)/', $version, $matches );
    $db_version = $matches[1] ?? '';

    if ( stripos( $version, 'postgres' ) !== false ) {
      return false;
    }

    return version_compare(
      $db_version,
      RequirementsConfig::MINIMUM_MYSQL_VERSION,
      '>='
    );
  }


}
