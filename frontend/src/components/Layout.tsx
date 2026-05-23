import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { usePageTitle } from '../usePageTitle';

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/databases': 'Database Records',
  '/about': 'About',
  '/login': 'Log In',
  '/register': 'Register',
};

export default function Layout() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const pageTitle = PAGE_TITLES[pathname];
  usePageTitle(pageTitle);

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          DB Allocation Utility
        </Link>
        <nav className="nav">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/databases">Databases</NavLink>
          <NavLink to="/about">About</NavLink>
        </nav>
        <div className="user-area">
          {user ? (
            <>
              <span className="user-email">{user.full_name || user.email}</span>
              <button type="button" className="btn btn-ghost" onClick={logout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-ghost">
                Log in
              </Link>
              <Link to="/register" className="btn btn-primary">
                Register
              </Link>
            </>
          )}
        </div>
      </header>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
