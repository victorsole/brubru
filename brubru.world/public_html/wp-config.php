<?php
define( 'WP_CACHE', true ); // By Speed Optimizer by SiteGround

/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the web site, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * Localized language
 * * ABSPATH
 *
 * @link https://wordpress.org/support/article/editing-wp-config-php/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', 'db2zxcy74znirq' );

/** Database username */
define( 'DB_USER', 'ue0e8gucsgbba' );

/** Database password */
define( 'DB_PASSWORD', '27eg6aut0fzg' );

/** Database hostname */
define( 'DB_HOST', '127.0.0.1' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define( 'AUTH_KEY',          '1x`f01%^Au:A^&_n#tmL^Gno&Dq&hy3ae5WGPUYRbJ;;T8g}_h4MooIjL?kqk%zt' );
define( 'SECURE_AUTH_KEY',   'T{)S,fg/uH (Qw/aofS*W>tPu]}}FDb6V5(~~8J<2f^*gJDH$:@%[mak9_b#,,n*' );
define( 'LOGGED_IN_KEY',     '0p5&e9Y|<(.<gf=bZc%bg1UYz=j4n?vxD|2DMjHRb^)u%a.tnYZdt]V<kNS9RR&7' );
define( 'NONCE_KEY',         ',&z^1t 45DN[_+ayFajlX#{$<#Y{8}V1ZWaqQK<v6V109]yz@:e[3uycUDb}i=Fl' );
define( 'AUTH_SALT',         '@xQx~.)}yJ,jJUT,qC,%nOe2_@t+Z%:Iy.yL5 h<ifxdE|bMMG4C$*@~Y6L5RKDD' );
define( 'SECURE_AUTH_SALT',  '8ANmeh|ek2Zy7< ?am0|**kcRl([:!W-|UI(!bo_`O~v7O[>Q!& SOcKk*)wIPLE' );
define( 'LOGGED_IN_SALT',    'B~Ijj*(s~_4#yp:unGNudR;K8?&wPWBLTK+nGEo!lhrxPOWI3dd`^F)>l/z(#!?a' );
define( 'NONCE_SALT',        'MEChNrA<8qgzC-6p&Ghi(Npt<?>;lPj=C1R[yCPn`CTK<uN%2[;?(Y->d5O{F:MP' );
define( 'WP_CACHE_KEY_SALT', 'M17k)GMs96|HBa9BQ^EI73KI|d}zw!Kqggr2r){vDZ;U<dGHgUrhv+&udLbG:rv_' );


/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 */
$table_prefix = 'xnh_';


/* Add any custom values between this line and the "stop editing" line. */



/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://wordpress.org/support/article/debugging-in-wordpress/
 */
if ( ! defined( 'WP_DEBUG' ) ) {
	define( 'WP_DEBUG', false );
}

/* That's all, stop editing! Happy publishing. */

/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
@include_once('/var/lib/sec/wp-settings-pre.php'); // Added by SiteGround WordPress management system
require_once ABSPATH . 'wp-settings.php';
@include_once('/var/lib/sec/wp-settings.php'); // Added by SiteGround WordPress management system
