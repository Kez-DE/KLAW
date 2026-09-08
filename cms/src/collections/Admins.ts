// cms/src/collections/Admins.ts
import { APIError, type CollectionConfig, type PayloadRequest } from 'payload'
import {
  adminHoatDong,
  chiQuanTri,
  dangHoatDong,
  nenEpQuanTri,
  quanTriHoacChinhMinh,
  truongChiQuanTri,
} from '../access/vaiTro'
import { ghiNhatKyCms, ipCua } from '../hooks/nhatKyCms'

const QUAN_TRI_CUOI = 'Không thể hạ vai trò, vô hiệu hay xoá quản trị viên cuối cùng.'

/** Số quản trị viên đang hoạt động KHÁC `truId`. */
const soQuanTriKhac = async (req: PayloadRequest, truId: unknown): Promise<number> => {
  const { totalDocs } = await req.payload.count({
    collection: 'admins',
    where: {
      and: [
        { vai_tro: { equals: 'quan_tri' } },
        { hoat_dong: { not_equals: false } },
        { id: { not_equals: truId } },
      ],
    },
    overrideAccess: true,
  })
  return totalDocs
}

export const Admins: CollectionConfig = {
  slug: 'admins',
  labels: {
    singular: { vi: 'Quản trị viên', en: 'Admin' },
    plural: { vi: 'Quản trị viên', en: 'Admins' },
  },
  auth: {
    tokenExpiration: 8 * 60 * 60, // một ca làm việc
    maxLoginAttempts: 5,
    lockTime: 10 * 60 * 1000,
    cookies: { secure: process.env.NODE_ENV === 'production', sameSite: 'Lax' },
  },
  versions: false,
  admin: {
    useAsTitle: 'email',
    defaultColumns: ['email', 'ten', 'vai_tro', 'hoat_dong'],
    group: { vi: 'Hệ thống', en: 'System' },
  },
  access: {
    admin: ({ req }) => dangHoatDong(req.user),
    read: adminHoatDong,
    create: chiQuanTri,
    update: quanTriHoacChinhMinh,
    delete: chiQuanTri,
  },
  hooks: {
    afterLogin: [
      async ({ req, user }) => {
        await ghiNhatKyCms(req.payload, { hanh_dong: 'dang_nhap', boi: user.email, ip: ipCua(req) })
      },
    ],
    afterLogout: [
      async ({ req }) => {
        if (req.user) await ghiNhatKyCms(req.payload, { hanh_dong: 'dang_xuat', boi: req.user.email, ip: ipCua(req) })
      },
    ],
    beforeLogin: [
      ({ user }) => {
        if ((user as { hoat_dong?: boolean | null }).hoat_dong === false)
          throw new APIError('Tài khoản quản trị này đã bị vô hiệu.', 403)
      },
    ],
    beforeChange: [
      async ({ data, operation, originalDoc, req }) => {
        if (operation === 'create') {
          const { totalDocs } = await req.payload.count({
            collection: 'admins',
            overrideAccess: true,
          })
          if (nenEpQuanTri(totalDocs)) data.vai_tro = 'quan_tri' // create-first-user phải quản trị được
          return data
        }
        const haCap =
          originalDoc?.vai_tro === 'quan_tri' &&
          (data.vai_tro === 'doc' || data.hoat_dong === false)
        if (haCap && (await soQuanTriKhac(req, originalDoc.id)) === 0)
          throw new APIError(QUAN_TRI_CUOI, 400)
        return data
      },
    ],
    beforeDelete: [
      async ({ id, req }) => {
        const doc = await req.payload.findByID({ collection: 'admins', id, overrideAccess: true })
        if (doc.vai_tro === 'quan_tri' && (await soQuanTriKhac(req, id)) === 0)
          throw new APIError(QUAN_TRI_CUOI, 400)
      },
    ],
  },
  fields: [
    { name: 'ten', type: 'text', required: true, label: { vi: 'Tên', en: 'Name' } },
    {
      name: 'vai_tro',
      type: 'select',
      required: true,
      defaultValue: 'doc',
      label: { vi: 'Vai trò', en: 'Role' },
      options: [
        { label: { vi: 'Chỉ xem', en: 'Viewer' }, value: 'doc' },
        { label: { vi: 'Quản trị', en: 'Admin' }, value: 'quan_tri' },
      ],
      access: { update: truongChiQuanTri },
    },
    {
      name: 'hoat_dong',
      type: 'checkbox',
      defaultValue: true,
      label: { vi: 'Đang hoạt động', en: 'Active' },
      access: { update: truongChiQuanTri },
    },
  ],
}
