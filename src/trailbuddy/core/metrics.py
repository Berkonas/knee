"""Metric catalogue: units, evidence type and plain-language interpretation for every output.

Evidence types (shown as badges in the app and as a column in every export):
  measured  - directly measured by an instrument (force plate, load cell, scale, tape measure)
  video     - kinematic estimate from 2D video pose tracking
  model     - model-derived biomechanical estimate (depends on stated assumptions)
  scenario  - model-derived using an ASSUMED external force (sensitivity / what-if analysis)
  input     - value entered by the user
  unavailable - cannot be estimated credibly with the available data
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

KINDS = {
    "measured": "Measured",
    "video": "Video estimate (2D)",
    "model": "Model estimate",
    "scenario": "Scenario (assumed force)",
    "input": "User input",
    "unavailable": "Unavailable",
}


SHORT_KINDS = {"measured": "Measured", "video": "Video 2D", "model": "Model", "scenario": "Scenario",
               "input": "Input", "unavailable": "Unavailable"}


@dataclass(frozen=True)
class MetricInfo:
    label: str
    unit: str
    what: str
    why: str
    conclude: str
    not_conclude: str


INFO: dict[str, MetricInfo] = {
    "knee_flexion_peak": MetricInfo(
        "Peak knee flexion (stance)", "deg",
        "Largest 2D knee flexion angle while the analysed foot is on the step.",
        "Deeper knee flexion under load lengthens the lever arm between body weight and the knee, "
        "raising quadriceps demand during descent.",
        "Whether poles change how far the knee bends while supporting the body.",
        "Knee angle is movement, not load. A change in angle alone does not show a change in force."),
    "knee_flexion_rom": MetricInfo(
        "Knee flexion range of motion", "deg",
        "Max minus min 2D knee flexion over the analysis window.",
        "Describes the knee motion strategy used to lower the body.",
        "Whether the movement pattern differs between conditions.",
        "Not a loading measure."),
    "knee_flexion_at_contact": MetricInfo(
        "Knee flexion at foot contact", "deg",
        "2D knee flexion at the instant the analysed foot lands on the next step.",
        "Landing with a straighter knee transmits more impact; poles may let people land differently.",
        "Whether the landing strategy changes between conditions.",
        "Contact timing from video is approximate (+-1-2 frames)."),
    "knee_flexion_velocity_peak": MetricInfo(
        "Peak knee flexion velocity (loaded)", "deg/s",
        "Fastest rate of knee bending while the foot carries weight.",
        "A slower, more controlled lowering suggests the quadriceps are braking more smoothly.",
        "Whether pole use changes how quickly the knee 'gives' under load.",
        "Velocity amplifies tracking noise; filtering affects the value."),
    "hip_flexion_peak": MetricInfo(
        "Peak hip flexion (stance)", "deg", "Largest 2D hip flexion while the foot is loaded.",
        "Hip strategy can share the work of lowering the body with the knee.",
        "Whether load-sharing between hip and knee changes.", "2D projection; not hip load."),
    "ankle_dorsiflexion_peak": MetricInfo(
        "Peak ankle dorsiflexion (stance)", "deg", "Largest 2D ankle dorsiflexion while the foot is loaded.",
        "Stair descent relies heavily on ankle dorsiflexion to lower the body.",
        "Ankle strategy differences.", "MediaPipe foot landmarks are less precise than knee/hip."),
    "trunk_lean_mean": MetricInfo(
        "Mean trunk forward lean", "deg",
        "Average angle of the hip-to-shoulder line from vertical (+ = forward).",
        "Leaning forward moves the body's weight forward relative to the knee and can change knee "
        "and hip demands; poles may change posture.",
        "Postural strategy differences between conditions.",
        "Not a direct measure of back or hip load."),
    "shoulder_flexion_peak": MetricInfo(
        "Peak shoulder flexion", "deg",
        "Largest 2D angle of the upper arm forward of the trunk.",
        "Poles that are too long may force the arm higher, a more demanding posture.",
        "Whether pole length changes arm posture.",
        "Posture is not shoulder force or injury risk."),
    "elbow_flexion_mean": MetricInfo(
        "Mean elbow flexion", "deg",
        "Average 2D elbow flexion over the window.",
        "Pole length directly changes elbow angle (fit guideline ~90 deg on level ground).",
        "How pole length changes arm configuration.",
        "Not an elbow load measure."),
    "speed": MetricInfo(
        "Horizontal progression speed", "m/s",
        "Mean horizontal speed of the mid-hip over the window.",
        "Speed changes joint loads; differences may confound pole effects.",
        "Whether participants moved at similar speeds across conditions.",
        "Only the horizontal component; accuracy depends on the scale calibration."),
    "cadence": MetricInfo(
        "Cadence", "steps/min",
        "Steps per minute from detected foot contacts.",
        "Strategy/pace check; a confounder of load comparisons.",
        "Whether stepping rhythm changed with poles.",
        "Event detection from video is approximate (about +-1-2 frames)."),
    "step_time_mean": MetricInfo(
        "Mean step time", "s", "Time between contacts of alternating feet.",
        "Pace and rhythm.", "Rhythm differences.", "Approximate event timing from video."),
    "step_time_cv": MetricInfo(
        "Step time variability (CV)", "%",
        "Coefficient of variation of step time within the trial.",
        "Steadier stepping; higher variability can indicate less confident or less consistent descent.",
        "Consistency differences between conditions.", "Needs several steps; few steps give an unstable CV."),
    "stance_time_mean": MetricInfo(
        "Mean stance time (analysed leg)", "s", "Duration of each complete foot contact.",
        "Longer stance spreads load over time (affects impulse).", "Timing differences.",
        "Partial stances at clip edges are excluded."),
    "knee_ext_moment_peak": MetricInfo(
        "Peak knee extensor moment", "N·m/kg",
        "Largest internal knee extensor moment during stance, normalised to body mass.",
        "This is the rotational demand the quadriceps must resist while lowering the body.",
        "How much the knee extensor demand differs between conditions under the stated model.",
        "Net joint moment is not joint contact force; values depend on the force input and model."),
    "quad_force_peak": MetricInfo(
        "Peak quadriceps force estimate", "N",
        "Peak knee extensor moment divided by an assumed patellar tendon moment arm.",
        "Primary internal-load estimate required by the assignment; the quadriceps work "
        "eccentrically during descent.",
        "Relative change in estimated quadriceps demand between conditions.",
        "Absolute force is uncertain (moment arm, co-contraction ignored); it is a "
        "net-moment-equivalent estimate, not a measured muscle force."),
    "quad_force_peak_bw": MetricInfo(
        "Peak quadriceps force estimate", "x BW", "Peak quadriceps force / body weight.",
        "Size-independent comparison.", "Relative differences.", "Same limits as above."),
    "knee_ext_impulse_total": MetricInfo(
        "Cumulative knee extensor angular impulse", "N·m·s/kg",
        "Time integral of the knee extensor moment over all stance phases in the window "
        "(mechanical-demand metric).",
        "Captures both how large and how long the knee extensor demand is; cumulative-load "
        "concepts are used to compare repeated loading across tasks.",
        "Differences in accumulated knee extensor demand for the same descent.",
        "Not muscle fatigue, perceived exertion, injury risk or pain."),
    "knee_ext_impulse_per_step": MetricInfo(
        "Knee extensor angular impulse per step", "N·m·s/kg",
        "Cumulative knee extensor angular impulse divided by the number of stance phases.",
        "Average knee demand per step, comparable across trials with different numbers of steps.",
        "Per-step mechanical demand differences.", "Not fatigue; same model limitations as the moment."),
    "knee_ext_impulse_per_m": MetricInfo(
        "Knee extensor angular impulse per metre descended", "N·m·s/kg per m",
        "Cumulative impulse divided by vertical height descended in the window.",
        "Normalises demand to the amount of descent (per-unit-distance load).",
        "Demand per unit of descent, comparable across trials of different length.",
        "Requires stair geometry; same limitations as cumulative impulse."),
    "knee_neg_work": MetricInfo(
        "Knee negative (eccentric) work", "J/kg",
        "Integral of negative knee power; energy absorbed by the knee extensors.",
        "Descent requires absorbing energy; eccentric work is linked to muscle soreness after "
        "downhill exercise.",
        "Change in energy absorbed at the knee between conditions.",
        "Not metabolic cost or fatigue; depends on model and filtering."),
    "knee_power_absorption_peak": MetricInfo(
        "Peak knee power absorption", "W/kg",
        "Largest rate of energy absorption at the knee during stance (magnitude of the most negative power).",
        "Shows how hard the quadriceps brake the body at the moment of greatest demand.",
        "Change in peak eccentric braking demand between conditions.",
        "Depends on moment model and on differentiated angles (noise-sensitive); not fatigue."),
    "elbow_moment_peak": MetricInfo(
        "Peak elbow moment", "N·m",
        "Quasi-static internal elbow moment from the pole force at the hand.",
        "Shows whether knee unloading is 'paid for' at the arm.",
        "Relative arm demand under the stated pole force.",
        "Pole force is assumed unless measured; not an injury risk measure."),
    "shoulder_moment_peak": MetricInfo(
        "Peak shoulder moment", "N·m",
        "Quasi-static internal shoulder moment from the pole force at the hand and arm weight.",
        "Secondary effect: upper-body demand created by pole use.",
        "Relative shoulder demand under the stated pole force.",
        "Pole force is assumed unless measured; ignores arm dynamics."),
    "pole_support_fraction": MetricInfo(
        "Mean pole support during stance", "% BW",
        "Vertical pole force / body weight, averaged over the analysed foot's stance.",
        "How much body support moves from the legs to the arms.",
        "With measured pole force: real support sharing. With a scenario: the assumption used.",
        "Cannot be determined from ordinary video."),
    "pole_contact_time": MetricInfo(
        "Pole contact time per plant", "s", "Duration of stationary pole-tip intervals.",
        "Timing of arm support relative to foot contact.", "Planting technique differences.",
        "Requires pole tracking; awaiting validation on real pole videos."),
    "pole_angle_at_contact": MetricInfo(
        "Pole angle at contact", "deg",
        "Pole inclination from vertical at the start of each plant (+ = tip ahead).",
        "Pole angle determines how much of the pole force supports body weight.",
        "Technique differences.", "2D projection; requires pole tracking."),
    "tibiofemoral_compression": MetricInfo(
        "Tibiofemoral compression", "N",
        "Joint contact force between femur and tibia.",
        "A direct internal knee-loading outcome.",
        "-",
        "Not estimated: requires a musculoskeletal model with hamstring/gastrocnemius "
        "co-contraction and measured ground reaction forces (e.g. OpenSim with force-plate data)."),
}


# Report grouping (order matters: shown top to bottom).
CATEGORIES: dict[str, list[str]] = {
    "Knee load": ["quad_force_peak", "quad_force_peak_bw", "knee_ext_moment_peak", "knee_ext_impulse_total",
                  "knee_ext_impulse_per_step", "knee_ext_impulse_per_m", "knee_neg_work", "knee_power_absorption_peak",
                  "tibiofemoral_compression"],
    "Knee and leg movement": ["knee_flexion_peak", "knee_flexion_at_contact", "knee_flexion_velocity_peak",
                              "knee_flexion_rom", "hip_flexion_peak", "ankle_dorsiflexion_peak"],
    "Trunk, arms and poles": ["trunk_lean_mean", "shoulder_flexion_peak", "elbow_flexion_mean", "elbow_moment_peak",
                              "shoulder_moment_peak", "pole_support_fraction", "pole_contact_time",
                              "pole_angle_at_contact"],
    "Pace and rhythm": ["speed", "cadence", "step_time_mean", "step_time_cv", "stance_time_mean"],
}


@dataclass
class MetricValue:
    key: str
    value: float | None
    kind: str
    note: str = ""
    sd: float | None = None
    low: float | None = None     # sensitivity range
    high: float | None = None

    @property
    def info(self) -> MetricInfo:
        return INFO[self.key]

    def as_row(self) -> dict:
        d = asdict(self)
        i = self.info
        d.update(label=i.label, unit=i.unit, evidence=KINDS[self.kind])
        return d
