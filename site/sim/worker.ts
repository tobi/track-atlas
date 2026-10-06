import { MODELS, solve } from "./physics";
import { calibrate } from "./calibrate";
self.onmessage = (event: MessageEvent) => {
  const { id, road, car, references, action } = event.data;
  try {
    const fit =
      action === "fit"
        ? calibrate(road, car, references, (progress) =>
            self.postMessage({ id, progress }),
          )
        : null;
    const settings = fit?.car || car;
    const runs = MODELS.map((model) => solve(road, settings, model));
    self.postMessage({ id, runs, fit, car: settings });
  } catch (error) {
    self.postMessage({ id, error: String(error) });
  }
};
