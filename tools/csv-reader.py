import pandas as pd
import numpy as np
import requests

OPENROUTER_API_KEY = "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"

url = "https://openrouter.ai/api/v1/chat/completions"

def call_openrouter(prompt):
      response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-4o-mini",  # can swap models
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
      )
      return response.json()["choices"][0]["message"]["content"]

class CSVAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None

    def load_data(self):
        try:
            self.df = pd.read_csv(self.file_path)
            return {"status": "loaded", "rows": len(self.df)}
        except Exception as e:
            return {"error": str(e)}

    def validate(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        missing = self.df.isnull().sum().to_dict()
        dtypes = self.df.dtypes.astype(str).to_dict()

        return {
            "columns": list(self.df.columns),
            "shape": self.df.shape,
            "missing_values": missing,
            "dtypes": dtypes
        }

    def clean_data(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        self.df = self.df.drop_duplicates()

        for col in self.df.columns:
            if self.df[col].dtype in ['float64', 'int64']:
                self.df[col] = self.df[col].fillna(self.df[col].mean())
            else:
                self.df[col] = self.df[col].fillna(self.df[col].mode()[0])

        return {"status": "cleaned"}

    def get_summary(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        return self.df.describe(include='all').to_dict()

    def detect_trends(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        trends = {}

        for col in self.df.select_dtypes(include=np.number):
            series = self.df[col]

            if series.is_monotonic_increasing:
                trends[col] = "increasing"
            elif series.is_monotonic_decreasing:
                trends[col] = "decreasing"
            else:
                trends[col] = "fluctuating"

        return trends

    def correlation_analysis(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        return self.df.corr(numeric_only=True).to_dict()

    def group_analysis(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        results = {}

        categorical_cols = self.df.select_dtypes(include='object').columns
        numeric_cols = self.df.select_dtypes(include=np.number).columns

        for cat in categorical_cols:
            for num in numeric_cols:
                results[f"{num}_by_{cat}"] = self.df.groupby(cat)[num].mean().to_dict()

        return results

    def anomaly_detection(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        anomalies = {}

        for col in self.df.select_dtypes(include=np.number):
            mean = self.df[col].mean()
            std = self.df[col].std()

            outliers = self.df[(self.df[col] > mean + 2*std) | (self.df[col] < mean - 2*std)]
            anomalies[col] = len(outliers)

        return anomalies

    def generate_insights(self):
        if self.df is None:
            return {"error": "Data not loaded"}

        insights = []

        trends = self.detect_trends()
        anomalies = self.anomaly_detection()

        for col, trend in trends.items():
            insights.append(f"Column '{col}' shows a {trend} trend")

        for col, count in anomalies.items():
            if count > 0:
                insights.append(f"Column '{col}' has {count} anomalies")

        return insights

    def generate_report(self):
        return {
            "validation": self.validate(),
            "summary": self.get_summary(),
            "trends": self.detect_trends(),
            "correlations": self.correlation_analysis(),
            "groups": self.group_analysis(),
            "anomalies": self.anomaly_detection(),
            "insights": self.generate_insights()
        }
    

    
    def analyze_with_ai(self, report, user_query):
      prompt = f"""
      You are an AI data analyst.

      User query:
      {user_query}

      Data report:
      {report}

      Tasks:
      - Identify key trends
      - Highlight anomalies
      - Give actionable insights
      - Be concise and clear
      """
      return call_openrouter(prompt)
      
if __name__ == "__main__":
      analyzer = CSVAnalyzer("customers-100.csv")

      analyzer.load_data()
      analyzer.clean_data()

      report = analyzer.generate_report()

      ai_output = analyzer.analyze_with_ai(report, "Analyze business performance and suggest improvements")

      print(ai_output)
