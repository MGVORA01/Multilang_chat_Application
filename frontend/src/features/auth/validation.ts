/** Client-side registration checks (mirrors the backend rules for instant feedback). */

export type RegisterErrors = Partial<Record<'username' | 'email' | 'password' | 'display_name', string>>

export function validateRegister(f: {
  username: string
  email: string
  password: string
  display_name: string
}): RegisterErrors {
  const errors: RegisterErrors = {}
  if (!/^[a-zA-Z0-9_.]{3,32}$/.test(f.username)) errors.username = '3–32 letters, digits, "_" or "."'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) errors.email = 'Enter a valid email address'
  if (f.password.length < 8) errors.password = 'At least 8 characters'
  if (!f.display_name.trim()) errors.display_name = 'Required'
  return errors
}
