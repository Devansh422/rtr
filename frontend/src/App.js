import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { Toaster } from "@/components/ui/sonner";
import SmoothScroll from "@/components/SmoothScroll";
import { JoinProvider } from "@/context/JoinContext";
import { LocaleProvider } from "@/context/LocaleContext";
import { AdminAuthProvider, RequireAdmin } from "@/context/AdminAuthContext";
import { MemberAuthProvider, RequireMember } from "@/context/MemberAuthContext";
import Layout from "@/components/Layout";

// ---- Campaign site (pre-existing) ----
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

// ---- Platform modules ----
import Constitution from "@/pages/Constitution";
import ConstitutionArticle from "@/pages/ConstitutionArticle";
import Representatives from "@/pages/Representatives";
import RepresentativeProfile from "@/pages/RepresentativeProfile";
import MyRepresentatives from "@/pages/MyRepresentatives";
import Promises from "@/pages/Promises";
import ManifestoAccountability from "@/pages/ManifestoAccountability";
import ManifestoPromises from "@/pages/ManifestoPromises";
import ManifestoPromise from "@/pages/ManifestoPromise";
import ManifestoRti from "@/pages/ManifestoRti";
import ManifestoReplies from "@/pages/ManifestoReplies";
import ManifestoDocuments from "@/pages/ManifestoDocuments";
import ManifestoDashboard from "@/pages/ManifestoDashboard";
import States from "@/pages/States";
import StatePage from "@/pages/StatePage";
import CommonCause from "@/pages/CommonCause";
import Petitions from "@/pages/Petitions";
import PetitionDetail from "@/pages/PetitionDetail";
import Reports from "@/pages/Reports";
import ReportDetail from "@/pages/ReportDetail";
import Forum from "@/pages/Forum";
import ForumThread from "@/pages/ForumThread";
import Tools from "@/pages/Tools";
import ToolGenerator from "@/pages/ToolGenerator";
import Academy from "@/pages/Academy";
import CoursePage from "@/pages/CoursePage";
import LessonPage from "@/pages/LessonPage";
import QuizPage from "@/pages/QuizPage";
import Research from "@/pages/Research";
import VolunteerPortal from "@/pages/VolunteerPortal";
import Events from "@/pages/Events";
import EventDetail from "@/pages/EventDetail";
import Assistant from "@/pages/Assistant";
import SiteSearch from "@/pages/SiteSearch";
import Docs from "@/pages/Docs";
import Legal from "@/pages/Legal";
import CertificateVerify from "@/pages/CertificateVerify";

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

          {/* Constitution Library */}
          <Route path="/constitution" element={<Constitution />} />
          <Route path="/constitution/:number" element={<ConstitutionArticle />} />

          {/* Accountability */}
          <Route path="/representatives" element={<Representatives />} />
          <Route path="/representatives/:slug" element={<RepresentativeProfile />} />
          <Route path="/my-representatives" element={<MyRepresentatives />} />
          <Route path="/promises" element={<Promises />} />

          {/* Manifesto accountability. The literal segments are declared before
              the state/year pattern, or "/manifesto/promises" would match it as
              state="promises". The long URL is the canonical one a promise page
              links to; the short /manifesto/promise/:code form exists for codes
              read off printed material and shared links. */}
          <Route path="/manifesto" element={<ManifestoAccountability />} />
          <Route path="/manifesto/promises" element={<ManifestoPromises />} />
          <Route path="/manifesto/rti" element={<ManifestoRti />} />
          <Route path="/manifesto/replies" element={<ManifestoReplies />} />
          <Route path="/manifesto/documents" element={<ManifestoDocuments />} />
          <Route path="/manifesto/dashboard" element={<ManifestoDashboard />} />
          <Route path="/manifesto/promise/:code" element={<ManifestoPromise />} />
          <Route path="/manifesto/:state/:year/:code" element={<ManifestoPromise />} />

          {/* States and the campaign dashboard */}
          <Route path="/states" element={<States />} />
          <Route path="/states/:slug" element={<StatePage />} />

          {/* Community. The national petition has its own page, singular: it is
              the one demand the whole platform points at, and the directory of
              member-started petitions is a different thing. */}
          <Route path="/petition" element={<CommonCause />} />
          <Route path="/petitions" element={<Petitions />} />
          <Route path="/petitions/:slug" element={<PetitionDetail />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/reports/:slug" element={<ReportDetail />} />
          <Route path="/forum" element={<Forum />} />
          <Route path="/forum/:slug" element={<ForumThread />} />

          {/* Civic tools. The `:key` route must come after the index. */}
          <Route path="/tools" element={<Tools />} />
          <Route path="/tools/:key" element={<ToolGenerator />} />

          {/* Knowledge. Order matters: /quiz would otherwise match :lessonSlug. */}
          <Route path="/academy" element={<Academy />} />
          <Route path="/academy/:slug" element={<CoursePage />} />
          <Route path="/academy/:slug/quiz" element={<QuizPage />} />
          <Route path="/academy/:slug/:lessonSlug" element={<LessonPage />} />
          <Route path="/research" element={<Research />} />

          {/* Participation */}
          <Route path="/volunteer-portal" element={<VolunteerPortal />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/:slug" element={<EventDetail />} />

          {/* Assistant, search, certificates */}
          <Route path="/ask" element={<Assistant />} />
          <Route path="/search" element={<SiteSearch />} />
          <Route path="/certificates" element={<CertificateVerify />} />
          <Route path="/certificates/:code" element={<CertificateVerify />} />

          {/* Plain-language guide to every feature */}
          <Route path="/docs" element={<Docs />} />

          {/* Published policies (§1, §7) */}
          <Route path="/privacy" element={<Legal kind="privacy" />} />
          <Route path="/content-policy" element={<Legal kind="content-policy" />} />
          <Route path="/disclaimer" element={<Legal kind="disclaimer" />} />

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
      {/* LocaleProvider wraps everything, including the admin panel: the language
          choice is a property of the person using the browser, not of one section. */}
      <LocaleProvider>
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
      </LocaleProvider>
      <Toaster position="top-center" richColors />
    </ThemeProvider>
  );
}

export default App;
