export default function About() {
  return (
    <div className="page about-page">
      <h1>About DB Allocation Utility</h1>
      <p>
        This application helps teams manage database allocation spreadsheets used for tracking
        CICS database pools, assignments, lifecycle, and release status.
      </p>
      <h2>Features</h2>
      <ul>
        <li>Import Excel files in the standard DB utility format (.xlsx)</li>
        <li>Export data back to Excel with the date appended to the filename</li>
        <li>Edit any field from the uploaded spreadsheet inline</li>
        <li>Delete individual database records</li>
        <li>Home page KPIs: expiring this month, prod mirror count, and more</li>
        <li>Email via Microsoft Outlook (SMTP): notify assignees and send expiry reports</li>
        <li>JIRA: link issue keys and add comments from the Databases page</li>
        <li>Secure login and user registration</li>
      </ul>
      <h2>Excel columns</h2>
      <p>
        Sheet row # (S.N. per sheet), Type, Database, # of CICS Trns, Prod Mirror, Release,
        Lifecycle, Status, Assignee, Team,
        Project, Start Date, End Date, Can be released -Y/N, Comments
      </p>
      <h2>Technology</h2>
      <ul>
        <li>React frontend (Yarn + Vite)</li>
        <li>Python FastAPI backend (uv)</li>
        <li>PostgreSQL database</li>
      </ul>
    </div>
  );
}
