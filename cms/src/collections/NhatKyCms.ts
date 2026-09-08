// cms/src/collections/NhatKyCms.ts
import type { CollectionConfig } from 'payload'
import { adminHoatDong } from '../access/vaiTro'

/** Nhật ký PHÍA CMS (spec §6.3): đăng nhập, đăng nhập sai, bản sao thao tác ghi qua proxy.
 *  Bản pháp lý nằm ở KLAW (`nhat_ky_quan_tri`); bảng này để tra trên giao diện. Chỉ hook ghi
 *  (`overrideAccess: true`); mọi đường access ghi đều đóng. */
export const NhatKyCms: CollectionConfig = {
  slug: 'nhat_ky_cms',
  labels: { singular: { vi: 'Nhật ký CMS', en: 'CMS log' }, plural: { vi: 'Nhật ký CMS', en: 'CMS logs' } },
  versions: false,
  admin: { hidden: true, useAsTitle: 'hanh_dong', defaultColumns: ['createdAt', 'hanh_dong', 'boi', 'ip'] },
  access: { read: adminHoatDong, create: () => false, update: () => false, delete: () => false },
  fields: [
    { name: 'hanh_dong', type: 'text', required: true, index: true },
    { name: 'boi', type: 'text', required: true, index: true },
    { name: 'ip', type: 'text' },
    { name: 'chi_tiet', type: 'json' },
  ],
}
