import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { Toaster } from "@/components/ui/sonner";
import SmoothScroll from "@/components/SmoothScroll";
import { JoinProvider } from "@/context/JoinContext";
import { AdminAuthProvider, RequireAdmin } from "@/context/AdminAuthContext";
import { MemberAuthProvider, RequireMember } from "@/context/MemberAuthContext";
import Layout from "@/components/Layout";
import Home from "@/pages/Home";
import About from "@/pages/About";
import Campaigns from "@/pages/Campaigns";
import CampaignDetail from "@/pages/CampaignDetail";
import Blog from "@/pages/Blog";
import BlogPost from "@/pages/BlogPost";
import Volunteer from "@/pages/Volunteer";
import Resources from "@/pages/Resources";
import Contact from "@/pages/Contact";
import SupporterFlow from "@/pages/SupporterFlow";
import KnowledgeHub from "@/pages/KnowledgeHub";
import AdminLogin from "@/pages/admin/AdminLogin";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import MemberLogin from "@/pages/MemberLogin";
import MemberDashboard from "@/pages/MemberDashboard";

function PublicApp() {
  return (
    <JoinProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/campaigns/:id" element={<CampaignDetail />} />
          <Route path="/blog" element={<Blog />} />
          <Route path="/blog/:id" element={<BlogPost />} />
          <Route path="/volunteer" element={<Volunteer />} />
          <Route path="/knowledge" element={<KnowledgeHub />} />
          <Route path="/resources" element={<Resources />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/join" element={<SupporterFlow />} />
          {/* Unknown public paths fall back to the home page. */}
          <Route path="*" element={<Home />} />
        </Routes>
      </Layout>
    </JoinProvider>
  );
}

function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
      <SmoothScroll>
        <BrowserRouter>
          <AdminAuthProvider>
            <MemberAuthProvider>
              <Routes>
                <Route path="/admin/login" element={<AdminLogin />} />
                <Route
                  path="/admin"
                  element={
                    <RequireAdmin>
                      <AdminDashboard />
                    </RequireAdmin>
                  }
                />
                <Route path="/login" element={<MemberLogin />} />
                <Route
                  path="/dashboard"
                  element={
                    <RequireMember>
                      <MemberDashboard />
                    </RequireMember>
                  }
                />
                <Route path="/*" element={<PublicApp />} />
              </Routes>
            </MemberAuthProvider>
          </AdminAuthProvider>
        </BrowserRouter>
      </SmoothScroll>
      <Toaster position="top-center" richColors />
    </ThemeProvider>
  );
}

export default App;
