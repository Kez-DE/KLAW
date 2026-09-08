// cms/src/access/vaiTro.ts
import type { Access, FieldAccess } from 'payload'

export type Admin = { id: number | string; email: string; vai_tro: 'doc' | 'quan_tri'; hoat_dong?: boolean | null }

export const dangHoatDong = (u: unknown): u is Admin =>
  typeof u === 'object' && u !== null && typeof (u as Admin).email === 'string' && (u as Admin).hoat_dong !== false
export const laQuanTri = (u: unknown): boolean => dangHoatDong(u) && u.vai_tro === 'quan_tri'

export const adminHoatDong: Access = ({ req }) => dangHoatDong(req.user)
export const chiQuanTri: Access = ({ req }) => laQuanTri(req.user)
export const quanTriHoacChinhMinh: Access = ({ req, id }) =>
  laQuanTri(req.user) || (dangHoatDong(req.user) && id !== undefined && String(req.user.id) === String(id))
export const truongChiQuanTri: FieldAccess = ({ req }) => laQuanTri(req.user)
