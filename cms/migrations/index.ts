import * as migration_20260908_184820_khoi_tao from './20260908_184820_khoi_tao';

export const migrations = [
  {
    up: migration_20260908_184820_khoi_tao.up,
    down: migration_20260908_184820_khoi_tao.down,
    name: '20260908_184820_khoi_tao'
  },
];
