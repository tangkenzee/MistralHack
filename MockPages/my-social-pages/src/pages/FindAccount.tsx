import { useState } from "react";
import { useNavigate } from "react-router-dom";
import BackButton from "@/components/BackButton";
import FooterLinks from "@/components/FooterLinks";

const FindAccount = () => {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex flex-col items-center pt-10 px-4">
        <div className="w-full max-w-[580px]">
          <BackButton />
          <h1 className="text-2xl font-bold text-foreground mb-1">Find Your Account</h1>
          <p className="text-sm text-muted-foreground mb-5">
            Enter your mobile number or email address.
          </p>
          <input
            type="text"
            placeholder="Mobile number or email address"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="w-full px-4 py-3.5 border border-border rounded-lg text-base bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            onClick={() => navigate("/choose-login")}
            className="w-full mt-4 py-3 rounded-lg bg-primary text-primary-foreground font-semibold text-base hover:opacity-90 transition-opacity"
          >
            Continue
          </button>
        </div>
      </main>
      <FooterLinks />
    </div>
  );
};

export default FindAccount;
