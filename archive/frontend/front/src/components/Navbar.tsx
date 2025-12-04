import { Link, NavLink } from "react-router-dom";
import "../theme.css";

export default function Navbar() {
  return (
    <header className="nav">
      <Link to="/" className="brand">contractextract</Link>
      <nav>
        <NavLink to="/upload" className={({isActive})=> isActive?"active":undefined}>Upload</NavLink>
        <NavLink to="/documents" className={({isActive})=> isActive?"active":undefined}>Documents</NavLink>
        <NavLink to="/rule-packs" className={({isActive})=> isActive?"active":undefined}>Rule Packs</NavLink>
      </nav>
    </header>
  );
}
